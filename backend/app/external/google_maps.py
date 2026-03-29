# backend/app/external/google_maps.py
"""
Google Maps API client — Geocoding + Nearby Search.
Cache key: geo:{vendor_name}:{city}, TTL: 86400s (24h).
Retry: 2 attempts, 2s backoff. Skip immediately on 429 quota error.
"""

from __future__ import annotations

import asyncio
import json
import logging
from decimal import Decimal
from typing import List, Optional

import httpx
import redis.asyncio as aioredis

from app.config import settings
from app.domain.models import GeoLocation, NearbyPlace

logger = logging.getLogger("trustflow.external.google_maps")

CACHE_TTL = 86400  # 24 hours


def _cache_key(vendor_name: str, city: str) -> str:
    """Build Redis cache key for geocoding result."""
    safe_vendor = vendor_name.lower().strip().replace(" ", "_")
    safe_city = city.lower().strip().replace(" ", "_")
    return f"geo:{safe_vendor}:{safe_city}"


def _get_redis() -> aioredis.Redis:
    """Create a Redis client for the app cache DB."""
    return aioredis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.CACHE_REDIS_DB,
        decode_responses=True,
    )


async def geocode_address(address: str, city: str = "") -> Optional[GeoLocation]:
    """
    Geocode an address using Google Maps Geocoding API.

    Checks Redis cache first. On miss, calls Google API.
    On failure or quota exceeded: returns None (graceful skip).

    Args:
        address: Address or vendor name to geocode.
        city: City qualifier for better results.

    Returns:
        GeoLocation with lat/lng, or None on failure.
    """
    full_address = f"{address} {city}".strip()
    cache_key_str = _cache_key(address, city) if city else f"geo:{address.lower().replace(' ', '_')}"
    r = _get_redis()

    try:
        # Check cache
        cached = await r.get(cache_key_str)
        if cached:
            data = json.loads(cached)
            logger.info("Geocode cache hit for '%s'", full_address)
            return GeoLocation(lat=Decimal(str(data["lat"])), lng=Decimal(str(data["lng"])))

        # Call API with retry
        location = await _call_geocode_api(full_address)
        if location:
            cache_data = json.dumps({"lat": str(location.lat), "lng": str(location.lng)})
            await r.setex(cache_key_str, CACHE_TTL, cache_data)
            return location

        return None

    except Exception as exc:
        logger.warning("Geocoding failed for '%s': %s", full_address, exc)
        return None
    finally:
        await r.aclose()


async def _call_geocode_api(address: str) -> Optional[GeoLocation]:
    """
    Call Google Maps Geocoding API with retry.

    2 attempts, 2s backoff. Skip on 429 quota error.

    Returns:
        GeoLocation or None.
    """
    params = {
        "address": address,
        "key": settings.GOOGLE_MAPS_API_KEY,
    }

    for attempt in range(1, 3):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                logger.info("Geocoding attempt %d: '%s'", attempt, address)
                response = await client.get(settings.GOOGLE_MAPS_GEOCODE_URL, params=params)

                if response.status_code == 429:
                    logger.warning("Google Maps quota exceeded — skipping geocoding")
                    return None

                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                if results:
                    geometry = results[0].get("geometry", {})
                    location = geometry.get("location", {})
                    if "lat" in location and "lng" in location:
                        return GeoLocation(
                            lat=Decimal(str(location["lat"])),
                            lng=Decimal(str(location["lng"])),
                        )

                logger.info("No geocoding results for '%s'", address)
                return None

        except httpx.HTTPError as exc:
            logger.warning("Geocoding attempt %d failed: %s", attempt, exc)
            if attempt < 2:
                await asyncio.sleep(2)

    return None


async def nearby_places(
    lat: Decimal,
    lng: Decimal,
    keyword: str,
    radius: int = 500,
) -> List[NearbyPlace]:
    """
    Search for nearby places using Google Maps Nearby Search API.

    Args:
        lat: Latitude of the search center.
        lng: Longitude of the search center.
        keyword: Search keyword (e.g., vendor name).
        radius: Search radius in meters (default 500).

    Returns:
        List of NearbyPlace results. Empty list on failure.
    """
    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "keyword": keyword,
        "key": settings.GOOGLE_MAPS_API_KEY,
    }

    for attempt in range(1, 3):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                logger.info("Nearby search attempt %d: '%s' at (%s, %s)", attempt, keyword, lat, lng)
                response = await client.get(settings.GOOGLE_MAPS_PLACES_URL, params=params)

                if response.status_code == 429:
                    logger.warning("Google Maps quota exceeded — skipping nearby search")
                    return []

                response.raise_for_status()
                data = response.json()

                places = []
                for result in data.get("results", []):
                    places.append(
                        NearbyPlace(
                            name=result.get("name", ""),
                            vicinity=result.get("vicinity", ""),
                            place_id=result.get("place_id", ""),
                        )
                    )
                return places

        except httpx.HTTPError as exc:
            logger.warning("Nearby search attempt %d failed: %s", attempt, exc)
            if attempt < 2:
                await asyncio.sleep(2)

    return []
