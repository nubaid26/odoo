# backend/app/services/gstin_service.py
"""
GSTIN service — wraps the external GSTIN client with business logic.
Handles GST_UNVERIFIED flag and trust score penalty implications.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from app.external.gstin import verify_gstin as _verify_gstin, validate_gstin_format
from app.domain.models import GSTINInfo

logger = logging.getLogger("trustflow.services.gstin")


async def verify_and_evaluate(
    gstin: str,
    amount: Decimal,
) -> dict:
    """
    Verify a GSTIN and evaluate its impact on trust scoring.

    Args:
        gstin: The GSTIN number to verify.
        amount: Expense amount in INR.

    Returns:
        Dict with:
        - gstin_info: GSTINInfo result
        - gst_verified: bool (API-verified as Active)
        - gst_unverified: bool (regex-only due to API failure)
        - gst_active: bool (status is Active)
        - check_type: str for bill_validation_logs
    """
    if not gstin:
        return {
            "gstin_info": GSTINInfo(status="missing"),
            "gst_verified": False,
            "gst_unverified": False,
            "gst_active": False,
            "check_type": "GST_MISSING",
        }

    info = await _verify_gstin(gstin, amount)

    if info.status == "GST_UNVERIFIED":
        return {
            "gstin_info": info,
            "gst_verified": False,
            "gst_unverified": True,
            "gst_active": False,
            "check_type": "GST_UNVERIFIED",
        }

    if info.status == "invalid_format":
        return {
            "gstin_info": info,
            "gst_verified": False,
            "gst_unverified": False,
            "gst_active": False,
            "check_type": "GST_INVALID_FORMAT",
        }

    if info.status == "regex_verified":
        return {
            "gstin_info": info,
            "gst_verified": False,
            "gst_unverified": True,
            "gst_active": True,
            "check_type": "GST_REGEX_ONLY",
        }

    return {
        "gstin_info": info,
        "gst_verified": info.is_active,
        "gst_unverified": False,
        "gst_active": info.is_active,
        "check_type": "GST_API_VERIFIED" if info.is_active else "GST_INACTIVE",
    }
