from __future__ import annotations


class EnergyMeter:
    """Utility for estimating model energy impact."""

    MODEL_JOULES_PER_TOKEN: dict[str, float] = {
        "gpt-4": 0.03,
        "gpt-4o": 0.024,
        "gpt-4o-mini": 0.012,
        "gpt-3.5-turbo": 0.004,
        "llama-3-70b": 0.01,
        "claude-3-opus": 0.022,
        "claude-3-sonnet": 0.015,
        "claude-3-haiku": 0.008,
        "mistral-large": 0.013,
        "phi-4": 0.007,
        "default": 0.01,
    }

    @classmethod
    def register_model(cls, model: str, joules_per_token: float) -> None:
        if joules_per_token <= 0:
            raise ValueError("joules_per_token must be positive")
        cls.MODEL_JOULES_PER_TOKEN[model] = joules_per_token

    @classmethod
    def intensity_for_model(cls, model: str) -> float:
        return cls.MODEL_JOULES_PER_TOKEN.get(model, cls.MODEL_JOULES_PER_TOKEN["default"])

    @classmethod
    def calculate_energy(
        cls,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        efficiency_modifier: float = 1.0,
    ) -> float:
        prompt_tokens = max(prompt_tokens, 0)
        completion_tokens = max(completion_tokens, 0)
        intensity = cls.intensity_for_model(model)
        total_tokens = prompt_tokens + completion_tokens
        energy_joules = total_tokens * intensity * max(efficiency_modifier, 0.1)
        return round(energy_joules, 6)
