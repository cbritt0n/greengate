from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.core.provider_settings import ProviderSettings


@dataclass(slots=True)
class ProviderResult:
    provider_name: str
    response: dict | None
    usage: dict
    energy_modifier: float
    stream: AsyncIterator[bytes] | None = None


class LLMProvider(ABC):
    def __init__(self, settings: ProviderSettings) -> None:
        self.settings = settings
        self.name = settings.name
        self.supported_models = set(settings.supported_models)
        self.energy_modifier = settings.energy_modifier

    def supports_model(self, model: str) -> bool:
        if not self.supported_models:
            return True
        return model in self.supported_models

    @abstractmethod
    async def invoke(self, payload: dict, *, stream: bool = False) -> ProviderResult:
        ...
