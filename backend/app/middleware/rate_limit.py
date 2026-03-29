# backend/app/middleware/rate_limit.py
"""
Rate limiting middleware using Redis sliding-window counter.
Parameterized per route. Returns 429 + Retry-After header on limit exceeded.
Gracefully skips rate limiting when Redis is unavailable (local dev).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

from fastapi import HTTPException, Request, status

from app.config import settings

logger = logging.getLogger("trustflow.middleware.rate_limit")


def _parse_rate_limit(rate_str: str) -> tuple:
    """
    Parse rate limit string like '5/15minute' or '3/hour' or '20/hour'.

    Returns (max_requests, window_seconds).
    """
    match = re.match(r"(\d+)/(\d*)\s*(second|minute|hour|day)s?", rate_str.strip())
    if not match:
        raise ValueError(f"Invalid rate limit format: {rate_str}")

    max_requests = int(match.group(1))
    multiplier = int(match.group(2)) if match.group(2) else 1

    unit_seconds = {
        "second": 1,
        "minute": 60,
        "hour": 3600,
        "day": 86400,
    }
    window_seconds = multiplier * unit_seconds[match.group(3)]

    return max_requests, window_seconds


async def check_rate_limit(
    key: str,
    rate_str: str,
) -> None:
    """
    Check and enforce rate limiting using Redis sliding window.

    Uses Redis INCR + EXPIRE pattern for atomic counter management.
    Silently skips if Redis is unavailable (local dev without Redis).

    Args:
        key: Unique identifier for the rate limit bucket.
        rate_str: Rate limit string (e.g., '5/15minute').

    Raises:
        HTTPException(429): When rate limit is exceeded, includes Retry-After header.
    """
    max_requests, window_seconds = _parse_rate_limit(rate_str)
    redis_key = f"ratelimit:{key}"

    try:
        import redis.asyncio as aioredis
        r = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.CACHE_REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=1,
        )
        try:
            pipe = r.pipeline()
            await pipe.incr(redis_key)
            await pipe.expire(redis_key, window_seconds)
            results = await pipe.execute()

            current_count = results[0]

            if current_count > max_requests:
                # Get TTL for Retry-After header
                ttl = await r.ttl(redis_key)
                retry_after = max(1, ttl)

                logger.warning(
                    "Rate limit exceeded for %s: %d/%d (retry after %ds)",
                    key, current_count, max_requests, retry_after,
                )

                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )

        finally:
            await r.aclose()
    except HTTPException:
        raise  # Re-raise 429 errors
    except Exception:
        # Redis unavailable — skip rate limiting in development
        logger.debug("Rate limiting skipped — Redis unavailable")


async def rate_limit_login(request: Request, email: str = "") -> None:
    """Rate limit login attempts: 5 per 15 minutes per IP+email."""
    client_ip = request.client.host if request.client else "unknown"
    key = f"login:{client_ip}:{email}"
    await check_rate_limit(key, settings.RATE_LIMIT_LOGIN)


async def rate_limit_signup(request: Request) -> None:
    """Rate limit signup: 3 per hour per IP."""
    client_ip = request.client.host if request.client else "unknown"
    key = f"signup:{client_ip}"
    await check_rate_limit(key, settings.RATE_LIMIT_SIGNUP)


async def rate_limit_expense_create(user_id: str) -> None:
    """Rate limit expense creation: 20 per hour per user_id."""
    key = f"expense_create:{user_id}"
    await check_rate_limit(key, settings.RATE_LIMIT_EXPENSE_CREATE)
