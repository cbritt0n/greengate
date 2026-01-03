from __future__ import annotations

from prometheus_client import Counter, Histogram

from app.core.config import settings

REQUEST_COUNTER = Counter(
    "greengate_requests_total",
    "Number of chat completion requests",
    labelnames=["provider", "cache", "status"],
)
ENERGY_SPENT = Histogram(
    "greengate_energy_joules",
    "Distribution of joules spent per request",
    buckets=(0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0, 200.0),
)
ENERGY_SAVED = Histogram(
    "greengate_energy_saved_joules",
    "Distribution of joules saved via cache hits",
    buckets=(0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0, 200.0),
)

PROVIDER_LATENCY_SECONDS = Histogram(
    "greengate_provider_latency_seconds",
    "Upstream provider request latency (seconds)",
    labelnames=["provider", "stream"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60),
)


def record_request(
    *,
    provider: str,
    cache_status: str,
    status: str,
    spent: float,
    saved: float,
) -> None:
    if not settings.PROMETHEUS_METRICS_ENABLED:
        return
    REQUEST_COUNTER.labels(provider=provider, cache=cache_status, status=status).inc()
    if spent > 0:
        ENERGY_SPENT.observe(spent)
    if saved > 0:
        ENERGY_SAVED.observe(saved)


def record_provider_latency(*, provider: str, seconds: float, stream: bool) -> None:
    if not settings.PROMETHEUS_METRICS_ENABLED:
        return
    PROVIDER_LATENCY_SECONDS.labels(
        provider=provider,
        stream="true" if stream else "false",
    ).observe(max(seconds, 0.0))
