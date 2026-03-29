# backend/app/services/currency_service.py
"""
Currency service — wraps the ExchangeRate API client with business logic.
Handles conversion, caching, and stale-cache fallback.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException

from app.external.exchange_rate import get_rate

logger = logging.getLogger("trustflow.services.currency")


async def convert_currency(
    amount: Decimal,
    from_currency: str,
    to_currency: str = "INR",
) -> dict:
    """
    Convert an amount from one currency to another.

    Calls the ExchangeRate API client (with Redis caching).
    Raises HTTP 503 if the rate is completely unavailable.

    Args:
        amount: Original amount.
        from_currency: Source ISO currency code.
        to_currency: Target ISO currency code (default INR).

    Returns:
        Dict with original_amount, original_currency, exchange_rate,
        converted_amount, and conversion_at.
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    # Same currency — no conversion needed
    if from_currency == to_currency:
        return {
            "original_amount": amount,
            "original_currency": from_currency,
            "exchange_rate": Decimal("1.000000"),
            "converted_amount": amount,
            "conversion_at": datetime.utcnow(),
        }

    try:
        rate = await get_rate(from_currency, to_currency)
        converted = (amount * rate).quantize(Decimal("0.01"))

        logger.info(
            "Converted %s %s → %s %s (rate: %s)",
            amount, from_currency, converted, to_currency, rate,
        )

        return {
            "original_amount": amount,
            "original_currency": from_currency,
            "exchange_rate": rate,
            "converted_amount": converted,
            "conversion_at": datetime.utcnow(),
        }

    except RuntimeError as exc:
        logger.error("Currency conversion failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Currency conversion unavailable: {from_currency} → {to_currency}",
        ) from exc
