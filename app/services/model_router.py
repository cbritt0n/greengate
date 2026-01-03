from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from fastapi import HTTPException, status

from app.core.config import settings
from app.providers.base import LLMProvider


@dataclass(slots=True)
class ProviderProfile:
    provider: LLMProvider
    cost_per_1k_tokens: float
    latency_ms: float
    reliability: float
    energy_modifier: float


class ModelRouter:
    def __init__(self, profiles: Iterable[ProviderProfile]):
        self.profiles: list[ProviderProfile] = list(profiles)
        self.weights = settings.router_weights()

    def select(self, model: str) -> ProviderProfile:
        eligible = [profile for profile in self.profiles if profile.provider.supports_model(model)]
        if not eligible:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No provider available for requested model",
            )
        scores = [(self._score(profile), profile) for profile in eligible]
        return max(scores, key=lambda pair: pair[0])[1]

    def _score(self, profile: ProviderProfile) -> float:
        cost = max(profile.cost_per_1k_tokens, 0.01)
        latency = max(profile.latency_ms, 0.1)
        reliability = min(max(profile.reliability, 0.5), 0.999)
        energy = max(profile.energy_modifier, 0.1)

        cost_factor = cost ** (-self.weights.get("cost", 0.25))
        latency_factor = latency ** (-self.weights.get("latency", 0.25))
        reliability_factor = reliability ** (self.weights.get("reliability", 0.25))
        energy_factor = (1 / energy) ** (self.weights.get("energy", 0.25))
        return cost_factor * latency_factor * reliability_factor * energy_factor


model_router: ModelRouter | None = None


def configure_router(providers: list[ProviderProfile]) -> ModelRouter:
    global model_router
    model_router = ModelRouter(providers)
    return model_router