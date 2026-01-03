from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from app.core.provider_settings import ProviderSettings
from app.providers.base import LLMProvider, ProviderResult


class OpenAIProvider(LLMProvider):
    def __init__(self, settings: ProviderSettings, client: httpx.AsyncClient) -> None:
        super().__init__(settings)
        self.client = client
        self.endpoint = f"{self.settings.base_url}/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }

    async def invoke(self, payload: dict, *, stream: bool = False) -> ProviderResult:
        request_payload = dict(payload)
        request_payload["stream"] = stream
        if stream:
            return await self._stream_response(request_payload)
        response = await self.client.post(self.endpoint, json=request_payload, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        usage: dict = data.get("usage", {})
        return ProviderResult(
            provider_name=self.name,
            response=data,
            usage=usage,
            energy_modifier=self.energy_modifier,
        )

    async def _stream_response(self, payload: dict) -> ProviderResult:
        stream = await self.client.stream("POST", self.endpoint, json=payload, headers=self.headers)

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
