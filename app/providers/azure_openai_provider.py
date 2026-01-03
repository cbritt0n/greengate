from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from app.core.provider_settings import ProviderSettings
from app.providers.base import LLMProvider, ProviderResult


class AzureOpenAIProvider(LLMProvider):
    def __init__(self, settings: ProviderSettings, client: httpx.AsyncClient) -> None:
        super().__init__(settings)
        self.client = client
        self.base_endpoint = settings.base_url.rstrip("/")
        self.api_version = str(settings.extras.get("api_version", "2024-07-01-preview"))
        self.deployments: dict[str, str] = {
            key: value for key, value in (settings.extras.get("deployments") or {}).items()
        }
        self.headers = {
            "api-key": settings.api_key,
            "Content-Type": "application/json",
        }

    async def invoke(self, payload: dict, *, stream: bool = False) -> ProviderResult:
        endpoint = self._endpoint_for_model(payload.get("model"))
        request_payload = dict(payload)
        request_payload["stream"] = stream
        if stream:
            return await self._stream_response(endpoint, request_payload)
        response = await self.client.post(endpoint, json=request_payload, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        usage: dict = data.get("usage", {})
        return ProviderResult(
            provider_name=self.name,
            response=data,
            usage=usage,
            energy_modifier=self.energy_modifier,
        )

    async def _stream_response(self, endpoint: str, payload: dict) -> ProviderResult:
        stream = await self.client.stream("POST", endpoint, json=payload, headers=self.headers)

        async def generator() -> AsyncIterator[bytes]:
            async with stream as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk

        return ProviderResult(
            provider_name=self.name,
            response=None,
            usage={},
            energy_modifier=self.energy_modifier,
            stream=generator(),
        )

    def _endpoint_for_model(self, model: str | None) -> str:
        if not model:
            raise ValueError("Azure OpenAI provider requires a model name")
        deployment = self.deployments.get(model, model)
        return (
            f"{self.base_endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={self.api_version}"
        )
