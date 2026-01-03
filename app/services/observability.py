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
