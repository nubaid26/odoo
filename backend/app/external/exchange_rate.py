# backend/app/external/exchange_rate.py
"""
ExchangeRate API client with Redis caching and stale-cache fallback.
Cache key: fx:{base}:{target}, TTL: 3600s.
Retry: 3 attempts with 2s/5s/10s backoff.
Stale cache fallback: up to 6 hours old. HTTP 503 on full failure.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from decimal import Decimal
from typing import Optional

import httpx
import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("trustflow.external.exchange_rate")

CACHE_TTL = 3600          # 1 hour
STALE_CACHE_MAX = 21600   # 6 hours
RETRY_DELAYS = [2, 5, 10]


def _cache_key(base: str, target: str) -> str:
    """Build Redis cache key for a currency pair."""
    return f"fx:{base.upper()}:{target.upper()}"


def _get_redis() -> aioredis.Redis:
    """Create a Redis client pointing at the app cache DB."""
    return aioredis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.CACHE_REDIS_DB,
        decode_responses=True,
    )


async def get_rate(base: str, target: str) -> Decimal:
    """
    Get the exchange rate from base to target currency.

    Checks Redis cache first. On miss, fetches from ExchangeRate API and caches.
    On API failure, serves stale cache if under 6 hours old, else raises HTTP 503.

    Args:
        base: Source currency code (e.g., "USD").
        target: Target currency code (e.g., "INR").

    Returns:
        Exchange rate as Decimal.

    Raises:
        httpx.HTTPStatusError: On non-retryable API errors.
        ValueError: If rate not found in API response.
        RuntimeError: If API unreachable and no stale cache available.
    """
    cache_key = _cache_key(base, target)
    r = _get_redis()

    try:
        # Check cache
        cached = await r.get(cache_key)
        if cached:
            data = json.loads(cached)
            logger.info("Cache hit for %s → %s: %s", base, target, data["rate"])
            return Decimal(str(data["rate"]))

        # Cache miss — fetch from API with retries
        rate = await _fetch_rate_with_retry(base, target)

        # Cache the result
        cache_data = json.dumps({"rate": str(rate), "fetched_at": time.time()})
        await r.setex(cache_key, CACHE_TTL, cache_data)
        logger.info("Fetched and cached rate %s → %s: %s", base, target, rate)
        return rate

    except Exception as exc:
        # Try stale cache fallback
        logger.warning("API failed for %s → %s, trying stale cache: %s", base, target, exc)
        stale = await r.get(cache_key)
        if stale:
            data = json.loads(stale)
            fetched_at = data.get("fetched_at", 0)
            age = time.time() - fetched_at
            if age < STALE_CACHE_MAX:
                logger.info("Serving stale cache for %s → %s (age: %.0fs)", base, target, age)
                return Decimal(str(data["rate"]))

        raise RuntimeError(
            f"Exchange rate unavailable for {base} → {target}. "
            f"API failed and no valid stale cache exists."
        ) from exc
    finally:
        await r.aclose()


async def _fetch_rate_with_retry(base: str, target: str) -> Decimal:
    """
    Fetch exchange rate from ExchangeRate API with retry logic.

    Retries 3 times with 2s, 5s, 10s backoff delays.

    Returns:
        Exchange rate as Decimal.

    Raises:
        RuntimeError: After all retries exhausted.
    """
    url = f"{settings.EXCHANGE_RATE_BASE_URL}/{base.upper()}"
    last_exc: Optional[Exception] = None

    for attempt, delay in enumerate(RETRY_DELAYS, start=1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                logger.info("Attempt %d: fetching rate from %s", attempt, url)
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                rates = data.get("rates", {})
                target_upper = target.upper()
                if target_upper not in rates:
                    raise ValueError(
                        f"Target currency {target_upper} not found in API response"
                    )

                return Decimal(str(rates[target_upper]))

        except (httpx.HTTPError, ValueError, KeyError) as exc:
            last_exc = exc
            logger.warning(
                "Attempt %d failed for %s → %s: %s. Retrying in %ds...",
                attempt, base, target, exc, delay,
            )
            if attempt < len(RETRY_DELAYS):
                await asyncio.sleep(delay)

    raise RuntimeError(
        f"ExchangeRate API failed after {len(RETRY_DELAYS)} attempts"
    ) from last_exc
