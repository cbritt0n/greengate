from __future__ import annotations

from collections.abc import Iterable

import tiktoken
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from app.core.energy import EnergyMeter
from app.dependencies import (
    get_cache_service,
    get_energy_ledger,
    get_proxy_service,
    get_rate_limiter,
    require_gateway_auth,
)
from app.schemas.chat import ChatCompletionRequest, ChatMessage
from app.services.cache_service import CacheHit, CacheService
from app.services.metrics_service import EnergyLedger
from app.services.observability import record_request
from app.services.proxy_service import ProxyService
from app.services.rate_limiter import RateLimiter

router = APIRouter()


@router.get("/v1/models")
async def list_models(_: None = Depends(require_gateway_auth)):
    """List models available through currently configured providers."""

    from app.core.config import settings

    model_providers: dict[str, set[str]] = {}
    for provider in settings.provider_configs():
        # If a provider doesn't specify supported_models, treat as "supports all" and
        # avoid listing an unbounded set.
        for model in provider.supported_models:
            model_providers.setdefault(model, set()).add(provider.name)

    data = [
        {
            "id": model,
            "object": "model",
            "providers": sorted(list(providers)),
        }
        for model, providers in sorted(model_providers.items())
    ]

    return {"object": "list", "data": data}


def _serialize_messages(messages: Iterable[ChatMessage]) -> str:
    return "\n".join(f"{message.role}:{message.content.strip()}" for message in messages)


def _count_tokens(text: str, model: str) -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def _estimate_usage(messages, completion_text: str, model: str) -> tuple[int, int]:
    prompt_text = "\n".join(message.content for message in messages)
    return _count_tokens(prompt_text, model), _count_tokens(completion_text, model)


def _safe_int(value: str | None) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


@router.post("/v1/chat/completions")
async def chat_completions(
    payload: ChatCompletionRequest,
    request: Request,
    response: Response,
    _: None = Depends(require_gateway_auth),
    cache_service: CacheService = Depends(get_cache_service),
    proxy: ProxyService = Depends(get_proxy_service),
    ledger: EnergyLedger = Depends(get_energy_ledger),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    identifier = payload.user or (request.client.host if request.client else "anonymous")
    await limiter.check(identifier)

    if payload.stream:
        return await _handle_streaming(payload, proxy, ledger)

    prompt_for_cache = _serialize_messages(payload.messages)

    cache_hit: CacheHit | None = await cache_service.get_cached_response(prompt_for_cache)
    if cache_hit:
        response.headers["X-GreenGate-Status"] = "CACHE_HIT"
        response.headers["X-GreenGate-Energy-Joules"] = "0.0"
        response.headers["X-GreenGate-Cache-Similarity"] = f"{cache_hit.similarity:.3f}"
        response.headers["X-GreenGate-Provider"] = cache_hit.metadata.get("provider", "cache")
        await ledger.record(
            spent=0.0,
            saved=cache_hit.estimated_energy,
            prompt_tokens=_safe_int(cache_hit.metadata.get("prompt_tokens")),
            completion_tokens=_safe_int(cache_hit.metadata.get("completion_tokens")),
        )
        record_request(
            provider=cache_hit.metadata.get("provider", "cache"),
            cache_status="hit",
            status="200",
            spent=0.0,
            saved=cache_hit.estimated_energy,
        )
        return cache_hit.response

    provider_result = await proxy.forward_request(
        payload.model_dump(exclude_none=True),
        stream=False,
    )

    llm_response = provider_result.response
    if llm_response is None:
        raise HTTPException(status_code=502, detail="Provider returned empty response")

    usage = provider_result.usage or llm_response.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)

    if prompt_tokens == 0 and completion_tokens == 0:
        completion_text = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "")
        prompt_tokens, completion_tokens = _estimate_usage(
            payload.messages,
            completion_text,
            payload.model,
        )

    energy_joules = EnergyMeter.calculate_energy(
        payload.model,
        prompt_tokens,
        completion_tokens,
        efficiency_modifier=provider_result.energy_modifier,
    )

    await cache_service.save_response(
        prompt_for_cache,
        llm_response,
        model=payload.model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        energy_joules=energy_joules,
        provider=provider_result.provider_name,
    )

    await ledger.record(
        spent=energy_joules,
        saved=0.0,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )

    record_request(
        provider=provider_result.provider_name,
        cache_status="miss",
        status="200",
        spent=energy_joules,
        saved=0.0,
    )

    response.headers["X-GreenGate-Status"] = "CACHE_MISS"
    response.headers["X-GreenGate-Energy-Joules"] = str(energy_joules)
    response.headers["X-GreenGate-Cache-Similarity"] = "0.000"
    response.headers["X-GreenGate-Provider"] = provider_result.provider_name

    return llm_response


async def _handle_streaming(
    payload: ChatCompletionRequest,
    proxy: ProxyService,
    ledger: EnergyLedger,
):
    provider_result = await proxy.forward_request(
        payload.model_dump(exclude_none=True),
        stream=True,
    )
    if provider_result.stream is None:
        raise HTTPException(status_code=502, detail="Provider does not support streaming")

    prompt_text = "\n".join(message.content for message in payload.messages)
    prompt_tokens = _count_tokens(prompt_text, payload.model)
    estimated_energy = EnergyMeter.calculate_energy(
        payload.model,
        prompt_tokens,
        completion_tokens=0,
        efficiency_modifier=provider_result.energy_modifier,
    )

    async def generator():
        try:
            async for chunk in provider_result.stream:
                yield chunk
        finally:
            await ledger.record(
                spent=estimated_energy,
                saved=0.0,
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
            )
            record_request(
                provider=provider_result.provider_name,
                cache_status="miss",
                status="200",
                spent=estimated_energy,
                saved=0.0,
            )

    headers = {
        "X-GreenGate-Status": "STREAMING",
        "X-GreenGate-Energy-Joules": str(estimated_energy),
        "X-GreenGate-Provider": provider_result.provider_name,
    }
    return StreamingResponse(generator(), media_type="text/event-stream", headers=headers)
