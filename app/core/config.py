from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.provider_settings import ProviderSettings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = Field("GreenGate")
    ENVIRONMENT: str = Field("development")
    OPENAI_API_KEY: str | None = None
    OPENAI_API_BASE: str = Field("https://api.openai.com/v1")
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_API_BASE: str = Field("https://api.anthropic.com/v1")
    COHERE_API_KEY: str | None = None
    COHERE_API_BASE: str = Field("https://api.cohere.ai")
    AZURE_OPENAI_API_KEY: str | None = None
    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_API_VERSION: str = Field("2024-07-01-preview")
    AZURE_OPENAI_DEPLOYMENT_MAP: str = Field(
        "",
        description=(
            "Comma-delimited model=deployment pairs "
            "(e.g., gpt-4o=my-deployment,gpt-4o-mini=mini)"
        ),
    )

    DATA_DIR: str = Field("data")
    CACHE_PERSIST_PATH: str | None = None
    LEDGER_DB_PATH: str | None = None

    CACHE_COLLECTION_NAME: str = Field("llm_cache")
    CACHE_SIMILARITY_THRESHOLD: float = Field(0.95, ge=0.0, le=1.0)
    CACHE_TOP_K: int = Field(3, ge=1)
    CACHE_MAX_RESULTS: int = Field(8, ge=1)

    HTTP_TIMEOUT_SECONDS: float = Field(60.0, gt=0)
    RETRY_ATTEMPTS: int = Field(3, ge=0)
    RETRY_BACKOFF_SECONDS: float = Field(0.5, gt=0)

    RATE_LIMIT_PER_MINUTE: int = Field(120, ge=1)
    ENERGY_TRACKING_ENABLED: bool = True
    PROMETHEUS_METRICS_ENABLED: bool = Field(True)
    OTEL_ENABLED: bool = Field(False)
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field("http://localhost:4318/v1/traces")
    OTEL_EXPORTER_OTLP_HEADERS: str = Field("", description="Comma-separated key=value entries")

    LOG_LEVEL: str = Field("INFO")
    MODEL_ROUTER_WEIGHTS: str = Field("cost=0.35,latency=0.2,reliability=0.3,energy=0.15")
    LLM_PROVIDER_SEQUENCE: str = Field("openai,anthropic,cohere,azure-openai")
    STREAMING_MAX_BUFFER_KB: int = Field(256, ge=64)

    # Optional gateway authentication (recommended for production)
    # If set, clients must send either:
    # - Authorization: Bearer <key>
    # - X-API-Key: <key>
    GATEWAY_API_KEY: str | None = None

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        return value.upper()

    def cache_path(self) -> Path:
        base = Path(self.CACHE_PERSIST_PATH or Path(self.DATA_DIR) / "cache")
        base.mkdir(parents=True, exist_ok=True)
        return base

    def ledger_path(self) -> Path:
        path = Path(self.LEDGER_DB_PATH or Path(self.DATA_DIR) / "energy.db")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def router_weights(self) -> dict[str, float]:
        defaults = {"cost": 0.35, "latency": 0.2, "reliability": 0.3, "energy": 0.15}
        try:
            pairs = [item.strip() for item in self.MODEL_ROUTER_WEIGHTS.split(",") if item.strip()]
            for pair in pairs:
                key, value = pair.split("=")
                defaults[key.strip()] = max(float(value.strip()), 0.0)
        except ValueError:
            pass
        total = sum(defaults.values()) or 1.0
        return {k: v / total for k, v in defaults.items()}

    def azure_deployments(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        entries = [
            item.strip()
            for item in self.AZURE_OPENAI_DEPLOYMENT_MAP.split(",")
            if item.strip()
        ]
        for entry in entries:
            try:
                model, deployment = entry.split("=")
                mapping[model.strip()] = deployment.strip()
            except ValueError:
                continue
        return mapping

    def otel_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        entries = [
            item.strip() for item in self.OTEL_EXPORTER_OTLP_HEADERS.split(",") if item.strip()
        ]
        for entry in entries:
            try:
                key, value = entry.split("=")
                headers[key.strip()] = value.strip()
            except ValueError:
                continue
        return headers

    def provider_configs(self) -> list[ProviderSettings]:
        providers: list[ProviderSettings] = []
        if self.OPENAI_API_KEY:
            providers.append(
                ProviderSettings(
                    name="openai",
                    kind="openai",
                    api_key=self.OPENAI_API_KEY,
                    base_url=self.OPENAI_API_BASE.rstrip("/"),
                    supported_models=[
                        "gpt-4",
                        "gpt-4o",
                        "gpt-4o-mini",
                        "gpt-4.1",
                        "gpt-3.5-turbo",
                        "o3-mini",
                    ],
                    energy_modifier=1.0,
                    latency_ms=650.0,
                    cost_per_1k_tokens=30.0,
                    reliability=0.995,
                )
            )
        if self.ANTHROPIC_API_KEY:
            providers.append(
                ProviderSettings(
                    name="anthropic",
                    kind="anthropic",
                    api_key=self.ANTHROPIC_API_KEY,
                    base_url=self.ANTHROPIC_API_BASE.rstrip("/"),
                    supported_models=[
                        "claude-3-opus",
                        "claude-3-sonnet",
                        "claude-3-haiku",
                        "claude-2.1",
                    ],
                    energy_modifier=0.85,
                    latency_ms=720.0,
                    cost_per_1k_tokens=24.0,
                    reliability=0.985,
                    extra_headers={"anthropic-version": "2023-06-01"},
                )
            )
        if self.COHERE_API_KEY:
            providers.append(
                ProviderSettings(
                    name="cohere",
                    kind="cohere",
                    api_key=self.COHERE_API_KEY,
                    base_url=self.COHERE_API_BASE.rstrip("/"),
                    supported_models=[
                        "command-r",
                        "command-r-plus",
                        "command-light",
                        "command",
                    ],
                    energy_modifier=0.9,
                    latency_ms=680.0,
                    cost_per_1k_tokens=18.0,
                    reliability=0.98,
                    extra_headers={"Cohere-Version": "2024-10-22"},
                )
            )
        if self.AZURE_OPENAI_API_KEY and self.AZURE_OPENAI_ENDPOINT:
            deployments = self.azure_deployments()
            providers.append(
                ProviderSettings(
                    name="azure-openai",
                    kind="azure_openai",
                    api_key=self.AZURE_OPENAI_API_KEY,
                    base_url=self.AZURE_OPENAI_ENDPOINT.rstrip("/"),
                    supported_models=list(deployments.keys()),
                    energy_modifier=1.05,
                    latency_ms=550.0,
                    cost_per_1k_tokens=28.0,
                    reliability=0.995,
                    extras={
                        "deployments": deployments,
                        "api_version": self.AZURE_OPENAI_API_VERSION,
                    },
                )
            )
        return providers


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
