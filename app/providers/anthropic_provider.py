from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from app.core.provider_settings import ProviderSettings
from app.providers.base import LLMProvider, ProviderResult


class AnthropicProvider(LLMProvider):
    def __init__(self, settings: ProviderSettings, client: httpx.AsyncClient) -> None:
        super().__init__(settings)
        self.client = client
        self.endpoint = f"{self.settings.base_url}/messages"
        self.headers = {
            "x-api-key": self.settings.api_key,
            "content-type": "application/json",
        }
        self.headers.update(self.settings.extra_headers)

    async def invoke(self, payload: dict, *, stream: bool = False) -> ProviderResult:
        transformed = self._transform_payload(payload, stream=stream)
        if stream:
            return await self._stream_response(transformed)
        response = await self.client.post(self.endpoint, json=transformed, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        usage = data.get("usage", {})
        return ProviderResult(
            provider_name=self.name,
            response=data,
            usage=usage,
            energy_modifier=self.energy_modifier,
        )

    def _transform_payload(self, payload: dict, stream: bool) -> dict:
        system_prompt = ""
        anthropic_messages: list[dict] = []
        for message in payload.get("messages", []):
            role = message.get("role")
            content = message.get("content", "")
            if role == "system":
                system_prompt = content
                continue
            anthropic_messages.append(
                {
                    "role": "assistant" if role == "assistant" else "user",
                    "content": [{"type": "text", "text": content}],
                }
            )

        return {
            "model": payload.get("model"),
            "messages": anthropic_messages,
            "max_tokens": payload.get("max_tokens", 1024),
            "temperature": payload.get("temperature", 1.0),
            "top_p": payload.get("top_p", 1.0),
            "system": system_prompt or "You are a climate-aware AI assistant.",
            "stream": stream,
        }

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
