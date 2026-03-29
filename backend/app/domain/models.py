# backend/app/domain/models.py
"""
Pydantic domain models — pure data contracts with no I/O, no DB, no HTTP.
All money values use Decimal, never float.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field


class MoneyAmount(BaseModel):
    """Represents a monetary amount with currency."""
    amount: Decimal = Field(..., description="Monetary value with 2 decimal places")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO 4217 currency code")


class OCRResult(BaseModel):
    """Result of local Tesseract OCR extraction."""
    raw_text: str = Field("", description="Full raw text extracted by Tesseract")
    parsed_amount: Optional[Decimal] = Field(None, description="Extracted monetary amount")
    parsed_date: Optional[str] = Field(None, description="Extracted date string")
    parsed_vendor: Optional[str] = Field(None, description="Extracted vendor name")
    parsed_gstin: Optional[str] = Field(None, description="Extracted GSTIN number")
    confidence: Decimal = Field(
        Decimal("0.0"),
        description="Ratio of successfully parsed fields to expected fields (0.0–1.0)",
    )


class ValidationCheckResult(BaseModel):
    """Result of a single validation check."""
    check_type: str
    passed: bool
    confidence: Decimal = Decimal("0.0")
    fraud_signal: bool = False
    message: str = ""


class ValidationResult(BaseModel):
    """Aggregate result of all validation checks for an expense."""
    checks: List[ValidationCheckResult] = Field(default_factory=list)
    passed_count: int = 0
    failed_count: int = 0

    @property
    def pass_rate(self) -> Decimal:
        """Return ratio of passed checks to total checks (0.0–1.0)."""
        total = self.passed_count + self.failed_count
        if total == 0:
            return Decimal("0.0")
        return Decimal(str(self.passed_count)) / Decimal(str(total))


class TrustInput(BaseModel):
    """Input data for trust score computation."""
    expense_id: str
    user_id: str
    company_id: str
    receipt_pass_rate: Decimal = Decimal("0.0")
    gst_verified: bool = False
    gst_active: bool = False
    gst_unverified: bool = False
    vendor_exact_match: bool = False
    vendor_fuzzy_match: bool = False
    vendor_fuzzy_ratio: Decimal = Decimal("0.0")
    fraud_signals_90d: int = 0
    is_first_expense: bool = False
    proof_type: str = "none"


class TrustResult(BaseModel):
    """Output of trust score computation."""
    score: Decimal
    grade: str
    receipt_score: Decimal
    gst_score: Decimal
    vendor_score: Decimal
    behavior_score: Decimal
    proof_score: Decimal
    formula_version: str = "v1.0"
    input_hash: str = ""
    weights_json: str = ""


class GSTINInfo(BaseModel):
    """Parsed GSTIN API response fields."""
    trade_name: str = ""
    status: str = ""
    registration_date: str = ""
    constitution: str = ""
    is_active: bool = False


class GeoLocation(BaseModel):
    """Geographic coordinates."""
    lat: Decimal
    lng: Decimal


class NearbyPlace(BaseModel):
    """Result from Google Maps Nearby Search."""
    name: str
    vicinity: str = ""
    place_id: str = ""
    match_ratio: Decimal = Decimal("0.0")
