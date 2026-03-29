# backend/tests/test_validation_service.py
"""
Validation service tests — unit tests for each of the four check types.
External clients (GSTIN API, Google Maps) are mocked.
"""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio

from app.db.models import Expense, ExpenseProof, BillValidationLog
from app.domain.models import ValidationCheckResult, GSTINInfo, GeoLocation, NearbyPlace


class TestMathCheck:
    """Math check: OCR amount vs submitted amount."""

    @pytest.mark.asyncio
    async def test_exact_match_passes(self, test_session, seed_company, seed_employee):
        """Exact amount match should pass."""
        expense = Expense(
            id="exp-math-1",
            user_id=seed_employee.id,
            company_id=seed_company.id,
            original_amount=Decimal("1500.00"),
            original_currency="INR",
            category="travel",
            idempotency_key="idem-math-1",
            status="DRAFT",
        )
        test_session.add(expense)

        proof = ExpenseProof(
            id="proof-math-1",
            expense_id="exp-math-1",
            proof_type="receipt",
            ocr_parsed_amount=Decimal("1500.00"),
            ocr_parsed_date="15/01/2025",
            ocr_confidence=Decimal("0.75"),
        )
        test_session.add(proof)
        await test_session.flush()

        from app.services.validation_service import _check_math
        result = await _check_math(test_session, expense, proof)

        assert result.passed is True
        assert result.fraud_signal is False
        assert result.check_type == "MATH_CHECK"

    @pytest.mark.asyncio
    async def test_within_tolerance_passes(self, test_session, seed_company, seed_employee):
        """Amount within 2% tolerance should pass."""
        expense = Expense(
            id="exp-math-2",
            user_id=seed_employee.id,
            company_id=seed_company.id,
            original_amount=Decimal("1000.00"),
            original_currency="INR",
            category="travel",
            idempotency_key="idem-math-2",
            status="DRAFT",
        )
        test_session.add(expense)

        proof = ExpenseProof(
            id="proof-math-2",
            expense_id="exp-math-2",
            proof_type="receipt",
            ocr_parsed_amount=Decimal("1015.00"),  # 1.5% delta
        )
        test_session.add(proof)
        await test_session.flush()

        from app.services.validation_service import _check_math
        result = await _check_math(test_session, expense, proof)

        assert result.passed is True
        assert result.fraud_signal is False

    @pytest.mark.asyncio
    async def test_large_delta_fraud_signal(self, test_session, seed_company, seed_employee):
        """Delta > 20% should trigger fraud signal."""
        expense = Expense(
            id="exp-math-3",
            user_id=seed_employee.id,
            company_id=seed_company.id,
            original_amount=Decimal("1000.00"),
            original_currency="INR",
            category="travel",
            idempotency_key="idem-math-3",
            status="DRAFT",
        )
        test_session.add(expense)

        proof = ExpenseProof(
            id="proof-math-3",
            expense_id="exp-math-3",
            proof_type="receipt",
            ocr_parsed_amount=Decimal("1500.00"),  # 50% delta
        )
        test_session.add(proof)
        await test_session.flush()

        from app.services.validation_service import _check_math
        result = await _check_math(test_session, expense, proof)

        assert result.passed is False
        assert result.fraud_signal is True

    @pytest.mark.asyncio
    async def test_no_ocr_amount(self, test_session, seed_company, seed_employee):
        """Missing OCR amount should fail without fraud signal."""
        expense = Expense(
            id="exp-math-4",
            user_id=seed_employee.id,
            company_id=seed_company.id,
            original_amount=Decimal("1000.00"),
            original_currency="INR",
            category="travel",
            idempotency_key="idem-math-4",
            status="DRAFT",
        )
        test_session.add(expense)

        proof = ExpenseProof(
            id="proof-math-4",
            expense_id="exp-math-4",
            proof_type="receipt",
            ocr_parsed_amount=None,
        )
        test_session.add(proof)
        await test_session.flush()

        from app.services.validation_service import _check_math
        result = await _check_math(test_session, expense, proof)

        assert result.passed is False
        assert result.fraud_signal is False


class TestDateCheck:
    """Date check: within 90 days."""

    @pytest.mark.asyncio
    async def test_recent_date_passes(self, test_session, seed_company, seed_employee):
        """Date within 90 days should pass."""
        recent_date = (datetime.utcnow() - timedelta(days=30)).strftime("%d/%m/%Y")

        expense = Expense(
            id="exp-date-1",
            user_id=seed_employee.id,
            company_id=seed_company.id,
            original_amount=Decimal("500.00"),
            original_currency="INR",
            category="food",
            idempotency_key="idem-date-1",
            status="DRAFT",
        )
        test_session.add(expense)

        proof = ExpenseProof(
            id="proof-date-1",
            expense_id="exp-date-1",
            proof_type="receipt",
            ocr_parsed_date=recent_date,
        )
        test_session.add(proof)
        await test_session.flush()

        from app.services.validation_service import _check_date
        result = await _check_date(test_session, expense, proof)

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_old_date_fails(self, test_session, seed_company, seed_employee):
        """Date older than 90 days should fail."""
        old_date = (datetime.utcnow() - timedelta(days=120)).strftime("%d/%m/%Y")

        expense = Expense(
            id="exp-date-2",
            user_id=seed_employee.id,
            company_id=seed_company.id,
            original_amount=Decimal("500.00"),
            original_currency="INR",
            category="food",
            idempotency_key="idem-date-2",
            status="DRAFT",
        )
        test_session.add(expense)

        proof = ExpenseProof(
            id="proof-date-2",
            expense_id="exp-date-2",
            proof_type="receipt",
            ocr_parsed_date=old_date,
        )
        test_session.add(proof)
        await test_session.flush()

        from app.services.validation_service import _check_date
        result = await _check_date(test_session, expense, proof)

        assert result.passed is False


class TestGSTCheck:
    """GST check: API or regex verification."""

    @pytest.mark.asyncio
    async def test_no_gstin_fails(self, test_session, seed_company, seed_employee):
        """Missing GSTIN should fail."""
        expense = Expense(
            id="exp-gst-1",
            user_id=seed_employee.id,
            company_id=seed_company.id,
            original_amount=Decimal("6000.00"),
            converted_amount=Decimal("6000.00"),
            original_currency="INR",
            category="office",
            idempotency_key="idem-gst-1",
            status="DRAFT",
        )
        test_session.add(expense)

        proof = ExpenseProof(
            id="proof-gst-1",
            expense_id="exp-gst-1",
            proof_type="receipt",
            ocr_parsed_gstin=None,
        )
        test_session.add(proof)
        await test_session.flush()

        from app.services.validation_service import _check_gst
        result = await _check_gst(test_session, expense, proof)

        assert result.passed is False

    @pytest.mark.asyncio
    @patch("app.services.gstin_service._verify_gstin")
    async def test_verified_active_passes(self, mock_verify, test_session, seed_company, seed_employee):
        """API-verified active GSTIN should pass."""
        mock_verify.return_value = GSTINInfo(
            trade_name="Test Vendor",
            status="Active",
            is_active=True,
        )

        expense = Expense(
            id="exp-gst-2",
            user_id=seed_employee.id,
            company_id=seed_company.id,
            original_amount=Decimal("6000.00"),
            converted_amount=Decimal("6000.00"),
            original_currency="INR",
            category="office",
            idempotency_key="idem-gst-2",
            status="DRAFT",
        )
        test_session.add(expense)

        proof = ExpenseProof(
            id="proof-gst-2",
            expense_id="exp-gst-2",
            proof_type="receipt",
            ocr_parsed_gstin="27AAPFU0939F1ZV",
        )
        test_session.add(proof)
        await test_session.flush()

        from app.services.validation_service import _check_gst
        result = await _check_gst(test_session, expense, proof)

        assert result.passed is True


class TestGPSCheck:
    """GPS check: geocoding + nearby search + Haversine."""

    @pytest.mark.asyncio
    async def test_no_gps_fails(self, test_session, seed_company, seed_employee):
        """Missing GPS coordinates should fail."""
        expense = Expense(
            id="exp-gps-1",
            user_id=seed_employee.id,
            company_id=seed_company.id,
            original_amount=Decimal("500.00"),
            original_currency="INR",
            category="food",
            idempotency_key="idem-gps-1",
            status="DRAFT",
            gps_lat=None,
            gps_lng=None,
        )
        test_session.add(expense)
        await test_session.flush()

        from app.services.validation_service import _check_gps
        result = await _check_gps(test_session, expense)

        assert result.passed is False
        assert "No GPS" in result.message

    @pytest.mark.asyncio
    async def test_no_vendor_fails(self, test_session, seed_company, seed_employee):
        """Missing vendor name should fail GPS check."""
        expense = Expense(
            id="exp-gps-2",
            user_id=seed_employee.id,
            company_id=seed_company.id,
            original_amount=Decimal("500.00"),
            original_currency="INR",
            category="food",
            idempotency_key="idem-gps-2",
            status="DRAFT",
            gps_lat=Decimal("19.0760000"),
            gps_lng=Decimal("72.8777000"),
            vendor_name=None,
        )
        test_session.add(expense)
        await test_session.flush()

        from app.services.validation_service import _check_gps
        result = await _check_gps(test_session, expense)

        assert result.passed is False
        assert "No vendor" in result.message
