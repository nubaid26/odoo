# backend/tests/test_trust_service.py
"""
Trust service tests — parametrized across all grade thresholds.
Tests formula consistency, edge cases, and input hash determinism.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.models import TrustInput
from app.services.trust_service import compute_trust_score


def _make_input(**kwargs) -> TrustInput:
    """Helper to create TrustInput with defaults."""
    defaults = {
        "expense_id": "test-expense-001",
        "user_id": "test-user-001",
        "company_id": "test-company-001",
        "receipt_pass_rate": Decimal("0.75"),
        "gst_verified": False,
        "gst_active": False,
        "gst_unverified": False,
        "vendor_exact_match": False,
        "vendor_fuzzy_match": False,
        "vendor_fuzzy_ratio": Decimal("0.0"),
        "fraud_signals_90d": 0,
        "is_first_expense": False,
        "proof_type": "receipt",
    }
    defaults.update(kwargs)
    return TrustInput(**defaults)


class TestTrustScoreComputation:
    """Test the weighted trust score formula."""

    def test_high_grade_all_perfect(self):
        """Perfect inputs should yield HIGH grade (>= 80)."""
        inp = _make_input(
            receipt_pass_rate=Decimal("1.0"),
            gst_verified=True,
            gst_active=True,
            vendor_exact_match=True,
            fraud_signals_90d=0,
            is_first_expense=False,
            proof_type="receipt",
        )
        result = compute_trust_score(inp)
        assert result.score >= Decimal("80")
        assert result.grade == "HIGH"
        assert result.receipt_score == Decimal("100.00")
        assert result.gst_score == Decimal("100.00")
        assert result.vendor_score == Decimal("100.00")
        assert result.proof_score == Decimal("100.00")

    def test_medium_grade(self):
        """Moderate inputs should yield MEDIUM grade (60-79)."""
        inp = _make_input(
            receipt_pass_rate=Decimal("0.75"),
            gst_verified=False,
            gst_unverified=True,
            vendor_fuzzy_match=True,
            vendor_fuzzy_ratio=Decimal("0.7"),
            fraud_signals_90d=0,
            proof_type="receipt",
        )
        result = compute_trust_score(inp)
        assert Decimal("60") <= result.score < Decimal("80")
        assert result.grade == "MEDIUM"

    def test_low_grade(self):
        """Poor inputs should yield LOW grade (40-59)."""
        inp = _make_input(
            receipt_pass_rate=Decimal("0.5"),
            gst_verified=False,
            gst_unverified=False,
            vendor_fuzzy_match=False,
            fraud_signals_90d=2,
            proof_type="payment_proof",
        )
        result = compute_trust_score(inp)
        assert Decimal("40") <= result.score < Decimal("60")
        assert result.grade == "LOW"

    def test_blocked_grade(self):
        """Very poor inputs should yield BLOCKED grade (< 40)."""
        inp = _make_input(
            receipt_pass_rate=Decimal("0.0"),
            gst_verified=False,
            gst_unverified=False,
            vendor_fuzzy_match=False,
            fraud_signals_90d=5,
            proof_type="none",
        )
        result = compute_trust_score(inp)
        assert result.score < Decimal("40")
        assert result.grade == "BLOCKED"

    def test_all_zero_edge_case(self):
        """All zero inputs should yield BLOCKED with score near 0."""
        inp = _make_input(
            receipt_pass_rate=Decimal("0.0"),
            gst_verified=False,
            gst_unverified=False,
            vendor_exact_match=False,
            vendor_fuzzy_match=False,
            fraud_signals_90d=10,
            is_first_expense=False,
            proof_type="none",
        )
        result = compute_trust_score(inp)
        assert result.grade == "BLOCKED"
        assert result.score <= Decimal("20")

    def test_perfect_score_edge_case(self):
        """Perfect score should be 100.00."""
        inp = _make_input(
            receipt_pass_rate=Decimal("1.0"),
            gst_verified=True,
            gst_active=True,
            vendor_exact_match=True,
            fraud_signals_90d=0,
            is_first_expense=False,
            proof_type="receipt",
        )
        result = compute_trust_score(inp)
        assert result.score == Decimal("100.00")

    def test_first_expense_behavior_score(self):
        """First expense should get behavior_score = 70."""
        inp = _make_input(is_first_expense=True)
        result = compute_trust_score(inp)
        assert result.behavior_score == Decimal("70.00")

    def test_fraud_reduces_behavior_score(self):
        """Each fraud signal in 90d should reduce behavior by 10."""
        inp = _make_input(fraud_signals_90d=3, is_first_expense=False)
        result = compute_trust_score(inp)
        assert result.behavior_score == Decimal("70.00")  # 100 - 3*10

    def test_formula_consistency(self):
        """Same inputs should always produce identical results."""
        inp = _make_input(
            receipt_pass_rate=Decimal("0.8"),
            gst_verified=True,
            gst_active=True,
            vendor_fuzzy_match=True,
            vendor_fuzzy_ratio=Decimal("0.75"),
        )
        result1 = compute_trust_score(inp)
        result2 = compute_trust_score(inp)

        assert result1.score == result2.score
        assert result1.grade == result2.grade
        assert result1.input_hash == result2.input_hash

    def test_input_hash_determinism(self):
        """Input hash should be deterministic for same inputs."""
        inp = _make_input()
        result1 = compute_trust_score(inp)
        result2 = compute_trust_score(inp)
        assert result1.input_hash == result2.input_hash
        assert len(result1.input_hash) == 64  # SHA-256 hex

    def test_different_inputs_different_hash(self):
        """Different inputs should produce different hashes."""
        inp1 = _make_input(receipt_pass_rate=Decimal("0.5"))
        inp2 = _make_input(receipt_pass_rate=Decimal("0.9"))
        result1 = compute_trust_score(inp1)
        result2 = compute_trust_score(inp2)
        assert result1.input_hash != result2.input_hash

    def test_formula_version(self):
        """Formula version should be v1.0."""
        inp = _make_input()
        result = compute_trust_score(inp)
        assert result.formula_version == "v1.0"

    def test_proof_scores(self):
        """Verify proof type scoring."""
        for proof_type, expected in [
            ("receipt", Decimal("100.00")),
            ("payment_proof", Decimal("65.00")),
            ("witness_only", Decimal("55.00")),
            ("none", Decimal("20.00")),
        ]:
            inp = _make_input(proof_type=proof_type)
            result = compute_trust_score(inp)
            assert result.proof_score == expected, f"Failed for {proof_type}"

    def test_gst_scores(self):
        """Verify GST scoring scenarios."""
        # API verified active = 100
        inp = _make_input(gst_verified=True, gst_active=True)
        assert compute_trust_score(inp).gst_score == Decimal("100.00")

        # Unverified (regex only) = 60
        inp = _make_input(gst_unverified=True)
        assert compute_trust_score(inp).gst_score == Decimal("60.00")

        # Missing / inactive = 0
        inp = _make_input(gst_verified=False, gst_unverified=False)
        assert compute_trust_score(inp).gst_score == Decimal("0.00")

    def test_weights_json_valid(self):
        """weights_json should be valid JSON with correct keys."""
        inp = _make_input()
        result = compute_trust_score(inp)
        import json
        weights = json.loads(result.weights_json)
        assert "receipt" in weights
        assert "gst" in weights
        assert "vendor" in weights
        assert "behavior" in weights
        assert "proof" in weights
