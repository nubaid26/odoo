# backend/app/services/validation_service.py
"""
Validation service — runs four sequential checks on an expense:
1. Math check (OCR amount vs submitted)
2. Date check (within 90 days)
3. GST check (API or regex)
4. GPS check (geocoding + nearby search + Haversine)

Each check writes a row to bill_validation_logs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BillValidationLog, ExpenseProof, Expense
from app.domain.models import ValidationResult, ValidationCheckResult
from app.repositories import expense_repo
from app.services import gstin_service, maps_service

logger = logging.getLogger("trustflow.services.validation")


async def run_all_checks(
    session: AsyncSession,
    expense: Expense,
    proof: ExpenseProof,
) -> ValidationResult:
    """
    Run all four validation checks for an expense.

    Each check creates a bill_validation_logs entry.
    The aggregate result is returned for trust scoring.

    Args:
        session: Database session.
        expense: The expense being validated.
        proof: The expense proof with OCR results.

    Returns:
        ValidationResult with all check results.
    """
    checks = []

    # Check 1: Math check — OCR amount vs submitted amount
    math_result = await _check_math(session, expense, proof)
    checks.append(math_result)

    # Check 2: Date check — within 90 days
    date_result = await _check_date(session, expense, proof)
    checks.append(date_result)

    # Check 3: GST check — API or regex
    gst_result = await _check_gst(session, expense, proof)
    checks.append(gst_result)

    # Check 4: GPS check — geocoding + nearby + Haversine
    gps_result = await _check_gps(session, expense)
    checks.append(gps_result)

    passed = sum(1 for c in checks if c.passed)
    failed = sum(1 for c in checks if not c.passed)

    return ValidationResult(
        checks=checks,
        passed_count=passed,
        failed_count=failed,
    )


async def _check_math(
    session: AsyncSession,
    expense: Expense,
    proof: ExpenseProof,
) -> ValidationCheckResult:
    """
    Math check: compare OCR-parsed amount with submitted amount.

    Pass if within 2% tolerance. Fraud signal if delta > 20%.
    """
    check_type = "MATH_CHECK"
    ocr_amount = proof.ocr_parsed_amount
    submitted_amount = expense.original_amount

    if ocr_amount is None:
        result = ValidationCheckResult(
            check_type=check_type,
            passed=False,
            confidence=Decimal("0.0"),
            fraud_signal=False,
            message="OCR could not extract amount from receipt",
        )
    else:
        if submitted_amount == 0:
            delta_pct = Decimal("100.0")
        else:
            delta_pct = abs(ocr_amount - submitted_amount) / submitted_amount * 100

        passed = delta_pct <= Decimal("2.0")
        fraud_signal = delta_pct > Decimal("20.0")
        confidence = max(Decimal("0.0"), Decimal("1.0") - (delta_pct / Decimal("100.0")))

        result = ValidationCheckResult(
            check_type=check_type,
            passed=passed,
            confidence=confidence.quantize(Decimal("0.001")),
            fraud_signal=fraud_signal,
            message=f"OCR amount ₹{ocr_amount} vs submitted ₹{submitted_amount} (delta: {delta_pct:.1f}%)",
        )

    # Write to bill_validation_logs
    log_entry = BillValidationLog(
        expense_id=expense.id,
        check_type=result.check_type,
        passed=result.passed,
        confidence=result.confidence,
        fraud_signal=result.fraud_signal,
        message=result.message,
    )
    await expense_repo.create_validation_log(session, log_entry)
    return result


async def _check_date(
    session: AsyncSession,
    expense: Expense,
    proof: ExpenseProof,
) -> ValidationCheckResult:
    """
    Date check: verify OCR-parsed date is within 90 days of today.
    """
    check_type = "DATE_CHECK"
    ocr_date = proof.ocr_parsed_date

    if not ocr_date:
        result = ValidationCheckResult(
            check_type=check_type,
            passed=False,
            confidence=Decimal("0.0"),
            fraud_signal=False,
            message="OCR could not extract date from receipt",
        )
    else:
        parsed_date = _parse_date_string(ocr_date)
        if parsed_date is None:
            result = ValidationCheckResult(
                check_type=check_type,
                passed=False,
                confidence=Decimal("0.0"),
                fraud_signal=False,
                message=f"Could not parse date: {ocr_date}",
            )
        else:
            days_old = (datetime.utcnow() - parsed_date).days
            passed = 0 <= days_old <= 90
            fraud_signal = days_old > 180

            result = ValidationCheckResult(
                check_type=check_type,
                passed=passed,
                confidence=Decimal("1.0") if passed else Decimal("0.3"),
                fraud_signal=fraud_signal,
                message=f"Receipt date {ocr_date} is {days_old} days old (limit: 90 days)",
            )

    log_entry = BillValidationLog(
        expense_id=expense.id,
        check_type=result.check_type,
        passed=result.passed,
        confidence=result.confidence,
        fraud_signal=result.fraud_signal,
        message=result.message,
    )
    await expense_repo.create_validation_log(session, log_entry)
    return result


async def _check_gst(
    session: AsyncSession,
    expense: Expense,
    proof: ExpenseProof,
) -> ValidationCheckResult:
    """
    GST check: verify GSTIN via API (if above threshold) or regex.

    Above ₹5000 + GSTIN present → API verification.
    Below threshold → regex + state-code check only.
    API failure → GST_UNVERIFIED flag.
    """
    check_type = "GST_CHECK"
    gstin = proof.ocr_parsed_gstin
    amount = expense.converted_amount or expense.original_amount

    if not gstin:
        result = ValidationCheckResult(
            check_type=check_type,
            passed=False,
            confidence=Decimal("0.0"),
            fraud_signal=False,
            message="No GSTIN found on receipt",
        )
    else:
        gst_eval = await gstin_service.verify_and_evaluate(gstin, amount)
        info = gst_eval["gstin_info"]

        if gst_eval["gst_verified"] and gst_eval["gst_active"]:
            result = ValidationCheckResult(
                check_type=gst_eval["check_type"],
                passed=True,
                confidence=Decimal("1.0"),
                fraud_signal=False,
                message=f"GSTIN {gstin} verified as Active — {info.trade_name}",
            )
        elif gst_eval["gst_unverified"]:
            result = ValidationCheckResult(
                check_type=gst_eval["check_type"],
                passed=True,
                confidence=Decimal("0.6"),
                fraud_signal=False,
                message=f"GSTIN {gstin} format valid (API unavailable or below threshold)",
            )
        else:
            result = ValidationCheckResult(
                check_type=gst_eval["check_type"],
                passed=False,
                confidence=Decimal("0.0"),
                fraud_signal=True,
                message=f"GSTIN {gstin} verification failed: {info.status}",
            )

    log_entry = BillValidationLog(
        expense_id=expense.id,
        check_type=result.check_type,
        passed=result.passed,
        confidence=result.confidence,
        fraud_signal=result.fraud_signal,
        message=result.message,
    )
    await expense_repo.create_validation_log(session, log_entry)
    return result


async def _check_gps(
    session: AsyncSession,
    expense: Expense,
) -> ValidationCheckResult:
    """
    GPS check: geocode vendor address, compare with submitted coords,
    and search nearby places for fuzzy vendor match.
    """
    check_type = "GPS_CHECK"

    if not expense.gps_lat or not expense.gps_lng:
        result = ValidationCheckResult(
            check_type=check_type,
            passed=False,
            confidence=Decimal("0.0"),
            fraud_signal=False,
            message="No GPS coordinates submitted with expense",
        )
    elif not expense.vendor_name:
        result = ValidationCheckResult(
            check_type=check_type,
            passed=False,
            confidence=Decimal("0.0"),
            fraud_signal=False,
            message="No vendor name provided for GPS verification",
        )
    else:
        try:
            verification = await maps_service.verify_vendor_location(
                vendor_name=expense.vendor_name,
                city="",  # City extracted from vendor name context
                submitted_lat=expense.gps_lat,
                submitted_lng=expense.gps_lng,
            )

            if verification["vendor_verified"]:
                confidence = Decimal("1.0") if verification["exact_match"] else Decimal("0.7")
                result = ValidationCheckResult(
                    check_type=check_type,
                    passed=True,
                    confidence=confidence,
                    fraud_signal=False,
                    message=(
                        f"Vendor '{expense.vendor_name}' verified at submitted location "
                        f"(match ratio: {verification['fuzzy_match_ratio']:.2f}, "
                        f"distance: {verification['distance_meters']}m)"
                    ),
                )
            elif verification["gps_mismatch"]:
                result = ValidationCheckResult(
                    check_type=check_type,
                    passed=False,
                    confidence=Decimal("0.3"),
                    fraud_signal=True,
                    message=(
                        f"GPS mismatch: vendor '{expense.vendor_name}' is "
                        f"{verification['distance_meters']}m from submitted location"
                    ),
                )
            else:
                result = ValidationCheckResult(
                    check_type=check_type,
                    passed=False,
                    confidence=Decimal("0.3"),
                    fraud_signal=False,
                    message=f"Could not verify vendor '{expense.vendor_name}' at submitted location",
                )

        except Exception as exc:
            logger.warning("GPS check failed: %s — skipping", exc)
            result = ValidationCheckResult(
                check_type=check_type,
                passed=False,
                confidence=Decimal("0.0"),
                fraud_signal=False,
                message=f"GPS verification skipped: Maps API unavailable ({exc})",
            )

    log_entry = BillValidationLog(
        expense_id=expense.id,
        check_type=result.check_type,
        passed=result.passed,
        confidence=result.confidence,
        fraud_signal=result.fraud_signal,
        message=result.message,
    )
    await expense_repo.create_validation_log(session, log_entry)
    return result


def _parse_date_string(date_str: str) -> Optional[datetime]:
    """Try multiple date formats to parse a date string."""
    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None
