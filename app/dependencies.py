from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.core.config import settings
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


def require_gateway_auth(request: Request) -> None:
    """Optionally enforce an API key for the gateway.

    If `settings.GATEWAY_API_KEY` is not set, this is a no-op.
    """

    expected = settings.GATEWAY_API_KEY
    if not expected:
        return

    header_api_key = request.headers.get("x-api-key")
    auth_header = request.headers.get("authorization")
    bearer_token = None
    if auth_header and auth_header.lower().startswith("bearer "):
        bearer_token = auth_header.split(" ", 1)[1].strip()

    if header_api_key == expected or bearer_token == expected:
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
        headers={"WWW-Authenticate": "Bearer"},
    )
