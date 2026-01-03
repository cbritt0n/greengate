from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from app.core.provider_settings import ProviderSettings
from app.providers.base import LLMProvider, ProviderResult


class CohereProvider(LLMProvider):
    def __init__(self, settings: ProviderSettings, client: httpx.AsyncClient) -> None:
        super().__init__(settings)
        self.client = client
        self.endpoint = f"{self.settings.base_url}/v1/chat"
        self.headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
            **self.settings.extra_headers,
        }

    async def invoke(self, payload: dict, *, stream: bool = False) -> ProviderResult:
        request_payload = self._translate_payload(payload, stream=stream)
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

    def _translate_payload(self, payload: dict, *, stream: bool) -> dict:
        messages = payload.get("messages") or []
        converted: list[dict] = []
        for message in messages:
            role = str(message.get("role", "user")).upper()
            content = message.get("content", "")
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict):
                        text_parts.append(str(part.get("text") or part.get("content") or ""))
                    else:
                        text_parts.append(str(part))
                text = " ".join(filter(None, text_parts))
            else:
                text = str(content)
            converted.append({"role": role, "content": text})

        cohere_payload = {
            "model": payload.get("model"),
            "messages": converted,
            "temperature": payload.get("temperature"),
            "stream": stream,
        }
        if "max_tokens" in payload:
            cohere_payload["max_tokens"] = payload["max_tokens"]
        return {k: v for k, v in cohere_payload.items() if v is not None}
