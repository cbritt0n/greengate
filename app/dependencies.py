from __future__ import annotations

from app.services.cache_service import CacheService, cache_service
from app.services.metrics_service import EnergyLedger, energy_ledger
from app.services.proxy_service import ProxyService, proxy_service
from app.services.rate_limiter import RateLimiter, rate_limiter


def get_cache_service() -> CacheService:
    return cache_service


def get_proxy_service() -> ProxyService:
    return proxy_service


def get_energy_ledger() -> EnergyLedger:
    return energy_ledger


def get_rate_limiter() -> RateLimiter:
    if rate_limiter is None:
        raise RuntimeError("Rate limiter has not been configured")
    return rate_limiter
