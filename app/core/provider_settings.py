from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(slots=True)
class ProviderSettings:
    name: str
    kind: Literal["openai", "anthropic", "cohere", "azure_openai"]
    api_key: str
    base_url: str
    supported_models: list[str]
    energy_modifier: float = 1.0
    latency_ms: float = 800.0
    cost_per_1k_tokens: float = 15.0
    reliability: float = 0.98
    extra_headers: dict[str, str] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)
