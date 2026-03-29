# backend/app/external/gstin.py
"""
GSTIN verification API client.
Skips API call if amount <= GSTIN_VERIFY_THRESHOLD (regex-only).
Cache key: gstin:{number}, TTL: 604800s (7 days).
Retry: 2 attempts, 3s backoff. No retry on 404.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from decimal import Decimal
from typing import Optional

import httpx
import redis.asyncio as aioredis

from app.config import settings
from app.domain.models import GSTINInfo

logger = logging.getLogger("trustflow.external.gstin")

CACHE_TTL = 604800  # 7 days
GSTIN_REGEX = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
)
# State codes: 01–37 plus 97 for other territory
VALID_STATE_CODES = {str(i).zfill(2) for i in range(1, 38)} | {"97"}


def _cache_key(gstin: str) -> str:
    """Build Redis cache key for a GSTIN lookup."""
    return f"gstin:{gstin.upper()}"


def _get_redis() -> aioredis.Redis:
    """Create a Redis client for the app cache DB."""
    return aioredis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.CACHE_REDIS_DB,
        decode_responses=True,
    )


def validate_gstin_format(gstin: str) -> bool:
    """
    Validate GSTIN format using regex and state code check.

    Args:
        gstin: The GSTIN string to validate.

    Returns:
        True if the format matches, False otherwise.
    """
    if not gstin or len(gstin) != 15:
        return False
    if not GSTIN_REGEX.match(gstin.upper()):
        return False
    state_code = gstin[:2]
    return state_code in VALID_STATE_CODES


async def verify_gstin(gstin: str, amount: Decimal) -> GSTINInfo:
    """
    Verify a GSTIN number via the government API or regex-only check.

    If amount <= GSTIN_VERIFY_THRESHOLD: regex + state-code check only.
    If amount > threshold and GSTIN present: call API, cache result.
    If API unavailable: regex-only validation, flagged as GST_UNVERIFIED.

    Args:
        gstin: GSTIN number to verify.
        amount: Expense amount in INR for threshold comparison.

    Returns:
        GSTINInfo with verification results.
    """
    if not gstin:
        return GSTINInfo(status="missing", is_active=False)

    gstin = gstin.upper().strip()

    # Format check first
    if not validate_gstin_format(gstin):
        return GSTINInfo(
            status="invalid_format",
            is_active=False,
        )

    # Below threshold: regex-only
    if amount <= Decimal(str(settings.GSTIN_VERIFY_THRESHOLD)):
        logger.info("GSTIN %s below threshold ₹%s — regex-only check", gstin, amount)
        return GSTINInfo(
            status="regex_verified",
            is_active=True,  # Assumed valid based on format
        )

    # Above threshold: check cache then API
    r = _get_redis()
    try:
        cache_key = _cache_key(gstin)
        cached = await r.get(cache_key)
        if cached:
            data = json.loads(cached)
            logger.info("GSTIN %s cache hit", gstin)
            return GSTINInfo(**data)

        # Call GSTIN API
        info = await _call_gstin_api(gstin)
        if info:
            await r.setex(cache_key, CACHE_TTL, json.dumps(info.model_dump()))
            return info

        # API unavailable fallback
        logger.warning("GSTIN API unavailable for %s — regex-only fallback", gstin)
        return GSTINInfo(status="GST_UNVERIFIED", is_active=False)

    finally:
        await r.aclose()


async def _call_gstin_api(gstin: str) -> Optional[GSTINInfo]:
    """
    Call the GSTIN API with retry logic.

    Retry: 2 attempts, 3s backoff. No retry on 404 (invalid GSTIN).

    Args:
        gstin: The GSTIN number to look up.

    Returns:
        GSTINInfo on success, None on failure.
    """
    url = f"{settings.GSTIN_API_BASE_URL}/{gstin}"
    headers = {
        "x-api-key": settings.GSTIN_API_KEY,
        "Accept": "application/json",
    }

    for attempt in range(1, 3):  # 2 attempts
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                logger.info("GSTIN API attempt %d for %s", attempt, gstin)
                response = await client.get(url, headers=headers)

                if response.status_code == 404:
                    logger.info("GSTIN %s not found (404) — invalid", gstin)
                    return GSTINInfo(status="not_found", is_active=False)

                response.raise_for_status()
                data = response.json()

                return GSTINInfo(
                    trade_name=data.get("tradeNam", ""),
                    status=data.get("sts", ""),
                    registration_date=data.get("rgdt", ""),
                    constitution=data.get("ctb", ""),
                    is_active=data.get("sts", "").lower() == "active",
                )

        except httpx.HTTPError as exc:
            logger.warning("GSTIN API attempt %d failed: %s", attempt, exc)
            if attempt < 2:
                await asyncio.sleep(3)

    return None
