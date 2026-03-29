# backend/app/external/restcountries.py
"""
RestCountries API client — fetches country-currency mapping at startup.
Cache key: countries:currency_map, TTL: 86400s (24h).
Falls back to countries_fallback.json on API failure.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any

import httpx
import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("trustflow.external.restcountries")

CACHE_KEY = "countries:currency_map"
CACHE_TTL = 86400  # 24 hours
FALLBACK_PATH = Path(__file__).parent.parent.parent / "countries_fallback.json"


def _get_redis() -> aioredis.Redis:
    """Create a Redis client for the app cache DB."""
    return aioredis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.CACHE_REDIS_DB,
        decode_responses=True,
    )


async def fetch_and_cache_countries() -> Dict[str, Any]:
    """
    Fetch country-currency mapping from RestCountries API and cache in Redis.

    Called once at API startup via @app.on_event("startup").
    If the API call fails, loads from countries_fallback.json.

    Returns:
        Dict mapping country_name to {currency_code, currency_name}.
    """
    r = _get_redis()
    try:
        # Check cache first
        cached = await r.get(CACHE_KEY)
        if cached:
            logger.info("Country-currency map loaded from cache")
            return json.loads(cached)

        # Fetch from API
        currency_map = await _fetch_from_api()
        if currency_map:
            await r.setex(CACHE_KEY, CACHE_TTL, json.dumps(currency_map))
            logger.info("Cached %d country-currency entries from API", len(currency_map))
            return currency_map

        # Fallback to bundled JSON
        return await _load_fallback(r)

    except Exception as exc:
        logger.warning("RestCountries fetch failed: %s. Loading fallback.", exc)
        return await _load_fallback(r)
    finally:
        await r.aclose()


async def _fetch_from_api() -> Dict[str, Any]:
    """
    Fetch country data from RestCountries public API.

    Returns:
        Parsed dict of country_name -> {currency_code, currency_name}, or empty dict on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            logger.info("Fetching countries from %s", settings.COUNTRIES_API_URL)
            response = await client.get(settings.COUNTRIES_API_URL)
            response.raise_for_status()
            data = response.json()

            currency_map: Dict[str, Any] = {}
            for entry in data:
                country_name = entry.get("name", {}).get("common", "")
                currencies = entry.get("currencies", {})
                if country_name and currencies:
                    for code, info in currencies.items():
                        currency_map[country_name] = {
                            "currency_code": code,
                            "currency_name": info.get("name", ""),
                        }
                        break  # Take the first currency for each country

            return currency_map

    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.error("RestCountries API error: %s", exc)
        return {}


async def _load_fallback(r: aioredis.Redis) -> Dict[str, Any]:
    """
    Load country-currency data from the bundled fallback JSON file.

    Args:
        r: Redis client for caching the fallback data.

    Returns:
        Dict mapping country_name to {currency_code, currency_name}.
    """
    logger.info("Loading countries from fallback: %s", FALLBACK_PATH)
    with open(FALLBACK_PATH, "r", encoding="utf-8") as f:
        fallback_data = json.load(f)

    # Cache fallback data too
    await r.setex(CACHE_KEY, CACHE_TTL, json.dumps(fallback_data))
    logger.info("Loaded %d entries from fallback file", len(fallback_data))
    return fallback_data


async def get_cached_countries() -> Dict[str, Any]:
    """
    Retrieve the cached country-currency mapping from Redis.

    Returns:
        Dict mapping country_name to {currency_code, currency_name}.
    """
    r = _get_redis()
    try:
        cached = await r.get(CACHE_KEY)
        if cached:
            return json.loads(cached)
        # If not in cache, re-fetch
        return await fetch_and_cache_countries()
    finally:
        await r.aclose()
