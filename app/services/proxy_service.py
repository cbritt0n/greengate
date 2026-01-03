from __future__ import annotations

import asyncio

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.provider_settings import ProviderSettings
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.azure_openai_provider import AzureOpenAIProvider
from app.providers.base import LLMProvider, ProviderResult
from app.providers.cohere_provider import CohereProvider
from app.providers.openai_provider import OpenAIProvider
from app.services.model_router import ProviderProfile, configure_router, model_router


class ProxyService:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()
        self._router_lock = asyncio.Lock()
        self._profiles: list[ProviderProfile] = []

    async def initialize(self) -> None:
        if model_router is not None:
            return
        async with self._router_lock:
            if model_router is not None:
                return
            configs = settings.provider_configs()
            if not configs:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No LLM providers configured",
                )
            order = [
                name.strip() for name in settings.LLM_PROVIDER_SEQUENCE.split(",") if name.strip()
            ]
            configs.sort(key=lambda cfg: order.index(cfg.name) if cfg.name in order else len(order))
            client = await self._ensure_client()
            self._profiles = [self._create_profile(cfg, client) for cfg in configs]
            configure_router(self._profiles)

    def _create_profile(self, cfg: ProviderSettings, client: httpx.AsyncClient) -> ProviderProfile:
        provider: LLMProvider
        if cfg.kind == "openai":
            provider = OpenAIProvider(cfg, client)
        elif cfg.kind == "anthropic":
            provider = AnthropicProvider(cfg, client)
        elif cfg.kind == "cohere":
            provider = CohereProvider(cfg, client)
        elif cfg.kind == "azure_openai":
            provider = AzureOpenAIProvider(cfg, client)
        else:
            raise ValueError(f"Unsupported provider kind: {cfg.kind}")
        return ProviderProfile(
            provider=provider,
            cost_per_1k_tokens=cfg.cost_per_1k_tokens,
            latency_ms=cfg.latency_ms,
            reliability=cfg.reliability,
            energy_modifier=cfg.energy_modifier,
        )

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    self._client = httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS)
        return self._client

    async def forward_request(self, payload: dict, *, stream: bool = False) -> ProviderResult:
        if model_router is None:
            await self.initialize()
        if model_router is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Model router unavailable",
            )

        model = payload.get("model")
        if not model:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model is required")

        profile = model_router.select(model)
        attempt = 0
        backoff = settings.RETRY_BACKOFF_SECONDS
        while True:
            try:
                result = await profile.provider.invoke(payload, stream=stream)
                return result
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code >= 500 and attempt < settings.RETRY_ATTEMPTS:
                    attempt += 1
                    await asyncio.sleep(backoff * attempt)
                    continue
                raise HTTPException(
                    status_code=exc.response.status_code,
                    detail=exc.response.text,
                ) from exc
            except httpx.RequestError as exc:
                if attempt >= settings.RETRY_ATTEMPTS:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Proxy request failed: {exc}",
                    ) from exc
                attempt += 1
                await asyncio.sleep(backoff * attempt)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


proxy_service = ProxyService()
