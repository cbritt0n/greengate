from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.provider_settings import ProviderSettings
from app.providers.base import LLMProvider, ProviderResult
from app.services.model_router import ModelRouter, ProviderProfile


class DummyProvider(LLMProvider):
    def __init__(self, name: str, models: list[str]):
        super().__init__(
            ProviderSettings(
                name=name,
                kind="openai",
                api_key="test",
                base_url="https://example.com",
                supported_models=models,
            )
        )

    async def invoke(
        self,
        payload: dict,
        *,
        stream: bool = False,
    ) -> ProviderResult:  # pragma: no cover - not used
        raise NotImplementedError


def _profile(
    name: str,
    cost: float,
    latency: float,
    reliability: float,
    energy: float,
) -> ProviderProfile:
    provider = DummyProvider(name, ["gpt-4", "gpt-3.5-turbo"])
    return ProviderProfile(
        provider=provider,
        cost_per_1k_tokens=cost,
        latency_ms=latency,
        reliability=reliability,
        energy_modifier=energy,
    )


def test_router_prefers_high_score_provider(monkeypatch):
    router = ModelRouter([
        _profile("expensive", cost=50, latency=800, reliability=0.99, energy=1.2),
        _profile("efficient", cost=20, latency=600, reliability=0.97, energy=0.8),
    ])

    selection = router.select("gpt-4")

    assert selection.provider.name == "efficient"


def test_router_no_provider_raises():
    router = ModelRouter([_profile("alpha", cost=10, latency=500, reliability=0.9, energy=1.0)])

    with pytest.raises(HTTPException):
        router.select("non-existent")
