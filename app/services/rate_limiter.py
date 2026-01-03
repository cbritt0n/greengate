from __future__ import annotations

import asyncio
import time

from fastapi import HTTPException, status


class TokenBucket:
    def __init__(self, rate_per_minute: int) -> None:
        self.capacity = float(rate_per_minute)
        self.tokens = float(rate_per_minute)
        self.refill_rate_per_second = float(rate_per_minute) / 60.0
        self.timestamp = time.monotonic()

    def consume(self, tokens: float = 1.0) -> bool:
        now = time.monotonic()
        elapsed = now - self.timestamp
        self.timestamp = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate_per_second)
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class RateLimiter:
    def __init__(self, rate_per_minute: int) -> None:
        self.rate_per_minute = rate_per_minute
        self._lock = asyncio.Lock()
        self._buckets: dict[str, TokenBucket] = {}

    async def check(self, identifier: str) -> None:
        if not identifier:
            identifier = "anonymous"
        async with self._lock:
            bucket = self._buckets.get(identifier)
            if bucket is None:
                bucket = TokenBucket(self.rate_per_minute)
                self._buckets[identifier] = bucket
            if not bucket.consume():
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please retry shortly.",
                )


rate_limiter: RateLimiter | None = None


def configure_rate_limiter(rate_per_minute: int) -> RateLimiter:
    global rate_limiter
    rate_limiter = RateLimiter(rate_per_minute)
    return rate_limiter
