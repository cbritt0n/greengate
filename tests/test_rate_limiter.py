import pytest
from fastapi import HTTPException

from app.services.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_enforces_capacity():
    limiter = RateLimiter(rate_per_minute=2)
    await limiter.check("user")
    await limiter.check("user")
    with pytest.raises(HTTPException):
        await limiter.check("user")
