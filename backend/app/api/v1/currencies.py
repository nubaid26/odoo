# backend/app/api/v1/currencies.py
"""
Currency endpoint — GET /currencies.
Returns country-currency mapping for the expense form dropdown.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.external.restcountries import get_cached_countries

logger = logging.getLogger("trustflow.api.currencies")
router = APIRouter()


@router.get("")
async def list_currencies():
    """
    Get all country-currency mappings for the expense form dropdown.

    Data is fetched from RestCountries API at startup and cached in Redis.
    Falls back to countries_fallback.json if API is unavailable.

    Returns:
        Dict mapping country_name to {currency_code, currency_name}.
    """
    countries = await get_cached_countries()
    return countries
