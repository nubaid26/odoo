# backend/app/services/trust_service.py
"""
Trust score computation — deterministic, versioned formula.
Formula version: v1.0

trust_score = (
    receipt_score  * 0.40
  + gst_score      * 0.20
  + vendor_score   * 0.20
  + behavior_score * 0.10
  + proof_score    * 0.10
)

Grade thresholds:
  HIGH    >= 80
  MEDIUM  60–79
  LOW     40–59
  BLOCKED < 40

Input hash: SHA-256(sorted JSON of inputs + formula_version)
"""

from __future__ import annotations

import hashlib
import json
import logging
from decimal import Decimal

from app.domain.enums import TrustGrade, ProofType
from app.domain.models import TrustInput, TrustResult

logger = logging.getLogger("trustflow.services.trust")

FORMULA_VERSION = "v1.0"
WEIGHTS = {
    "receipt": Decimal("0.40"),
    "gst": Decimal("0.20"),
    "vendor": Decimal("0.20"),
    "behavior": Decimal("0.10"),
    "proof": Decimal("0.10"),
}


def compute_trust_score(trust_input: TrustInput) -> TrustResult:
    """
    Compute the weighted trust score from input signals.

    The formula is deterministic — same inputs always produce the same score.
    The input_hash provides tamper detection.

    Args:
        trust_input: TrustInput with all signal data.

    Returns:
        TrustResult with score, grade, and all component scores.
    """
    # ── Receipt score (0–100) ──
    receipt_score = Decimal(str(trust_input.receipt_pass_rate)) * Decimal("100")
    receipt_score = min(Decimal("100"), max(Decimal("0"), receipt_score))

    # ── GST score (0–100) ──
    if trust_input.gst_verified and trust_input.gst_active:
        gst_score = Decimal("100")
    elif trust_input.gst_unverified:
        gst_score = Decimal("60")
    else:
        gst_score = Decimal("0")

    # ── Vendor score (0–100) ──
    if trust_input.vendor_exact_match:
        vendor_score = Decimal("100")
    elif trust_input.vendor_fuzzy_match:
        ratio = float(trust_input.vendor_fuzzy_ratio)
        if ratio >= 0.85:
            vendor_score = Decimal("100")
        elif ratio >= 0.6:
            vendor_score = Decimal("70")
        else:
            vendor_score = Decimal("30")
    else:
        vendor_score = Decimal("30")

    # ── Behavior score (0–100) ──
    if trust_input.is_first_expense:
        behavior_score = Decimal("70")
    else:
        fraud_count = trust_input.fraud_signals_90d
        behavior_score = max(
            Decimal("0"),
            Decimal("100") - Decimal(str(fraud_count)) * Decimal("10"),
        )

    # ── Proof score (0–100) ──
    proof_type = trust_input.proof_type.lower()
    if proof_type == ProofType.RECEIPT.value:
        proof_score = Decimal("100")
    elif proof_type == ProofType.PAYMENT_PROOF.value:
        proof_score = Decimal("65")
    elif proof_type == ProofType.WITNESS_ONLY.value:
        proof_score = Decimal("55")
    else:
        proof_score = Decimal("20")

    # ── Weighted total ──
    total_score = (
        receipt_score * WEIGHTS["receipt"]
        + gst_score * WEIGHTS["gst"]
        + vendor_score * WEIGHTS["vendor"]
        + behavior_score * WEIGHTS["behavior"]
        + proof_score * WEIGHTS["proof"]
    ).quantize(Decimal("0.01"))

    # ── Grade ──
    grade = _determine_grade(total_score)

    # ── Input hash for tamper detection ──
    input_hash = _compute_input_hash(trust_input)

    # ── Weights JSON ──
    weights_json = json.dumps(
        {k: str(v) for k, v in WEIGHTS.items()},
        sort_keys=True,
    )

    result = TrustResult(
        score=total_score,
        grade=grade.value,
        receipt_score=receipt_score.quantize(Decimal("0.01")),
        gst_score=gst_score.quantize(Decimal("0.01")),
        vendor_score=vendor_score.quantize(Decimal("0.01")),
        behavior_score=behavior_score.quantize(Decimal("0.01")),
        proof_score=proof_score.quantize(Decimal("0.01")),
        formula_version=FORMULA_VERSION,
        input_hash=input_hash,
        weights_json=weights_json,
    )

    logger.info(
        "Trust score for expense %s: %.2f (%s) — receipt=%.0f gst=%.0f vendor=%.0f behavior=%.0f proof=%.0f",
        trust_input.expense_id,
        total_score,
        grade.value,
        receipt_score,
        gst_score,
        vendor_score,
        behavior_score,
        proof_score,
    )

    return result


def _determine_grade(score: Decimal) -> TrustGrade:
    """
    Determine trust grade from numeric score.

    HIGH    >= 80
    MEDIUM  60–79
    LOW     40–59
    BLOCKED < 40
    """
    if score >= Decimal("80"):
        return TrustGrade.HIGH
    elif score >= Decimal("60"):
        return TrustGrade.MEDIUM
    elif score >= Decimal("40"):
        return TrustGrade.LOW
    else:
        return TrustGrade.BLOCKED


def _compute_input_hash(trust_input: TrustInput) -> str:
    """
    Compute SHA-256 hash of trust inputs + formula version.

    Recomputing with same inputs must yield identical hash.
    """
    input_data = trust_input.model_dump()
    input_data["formula_version"] = FORMULA_VERSION
    serialized = json.dumps(input_data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
