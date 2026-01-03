from __future__ import annotations

import json

import httpx
import pytest

from app.core.provider_settings import ProviderSettings
from app.providers.azure_openai_provider import AzureOpenAIProvider


@pytest.mark.asyncio
async def test_azure_provider_maps_model_to_deployment():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/deployments/prod-gpt/chat/completions")
        body = json.loads(request.content)
        assert body["stream"] is False
        return httpx.Response(
            200,
            json={"usage": {"prompt_tokens": 1}},
            headers={"Content-Type": "application/json"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AzureOpenAIProvider(
            ProviderSettings(
                name="azure-openai",
                kind="azure_openai",
                api_key="key",
                base_url="https://azure.local",
                supported_models=["gpt-4o"],
                extras={"deployments": {"gpt-4o": "prod-gpt"}, "api_version": "2024-07-01-preview"},
            ),
            client,
        )
        result = await provider.invoke({"model": "gpt-4o", "messages": []})
        assert result.usage["prompt_tokens"] == 1


@pytest.mark.asyncio
async def test_azure_provider_requires_model():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = AzureOpenAIProvider(
            ProviderSettings(
                name="azure-openai",
                kind="azure_openai",
                api_key="key",
                base_url="https://azure.local",
                supported_models=[],
                extras={},
            ),
            client,
        )
        with pytest.raises(ValueError):
            await provider.invoke({})
