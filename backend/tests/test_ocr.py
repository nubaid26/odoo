# backend/tests/test_ocr.py
"""
OCR extraction tests — unit tests for tesseract text parsing.
Uses mocked pytesseract to avoid requiring actual Tesseract binary.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch, MagicMock
from io import BytesIO

import pytest


class TestOCRParsing:
    """Test OCR text parsing functions (amount, date, vendor, GSTIN)."""

    def test_parse_amount_inr_symbol(self):
        """Amount with ₹ symbol should be extracted."""
        from app.external.tesseract import _parse_amount
        assert _parse_amount("Total: ₹1,500.50") == Decimal("1500.50")

    def test_parse_amount_rs_prefix(self):
        """Amount with Rs. prefix should be extracted."""
        from app.external.tesseract import _parse_amount
        assert _parse_amount("Amount: Rs. 2,300") == Decimal("2300")

    def test_parse_amount_usd(self):
        """Amount with $ symbol should be extracted."""
        from app.external.tesseract import _parse_amount
        assert _parse_amount("Total $45.99") == Decimal("45.99")

    def test_parse_amount_total_keyword(self):
        """Amount after 'Total:' keyword should be extracted."""
        from app.external.tesseract import _parse_amount
        assert _parse_amount("Grand Total: 3500.00") == Decimal("3500.00")

    def test_parse_amount_largest_value(self):
        """Should return the largest amount (likely the total)."""
        from app.external.tesseract import _parse_amount
        text = "Rs. 100\nRs. 200\nTotal: Rs. 300"
        assert _parse_amount(text) == Decimal("300")

    def test_parse_amount_no_match(self):
        """No amount in text should return None."""
        from app.external.tesseract import _parse_amount
        assert _parse_amount("No amounts here") is None

    def test_parse_date_dd_mm_yyyy(self):
        """Date in DD/MM/YYYY format."""
        from app.external.tesseract import _parse_date
        assert _parse_date("Date: 15/01/2025") == "15/01/2025"

    def test_parse_date_yyyy_mm_dd(self):
        """Date in YYYY-MM-DD format."""
        from app.external.tesseract import _parse_date
        assert _parse_date("Date: 2025-01-15") == "2025-01-15"

    def test_parse_date_dd_dash_mm_dash_yyyy(self):
        """Date in DD-MM-YYYY format."""
        from app.external.tesseract import _parse_date
        assert _parse_date("Invoice date: 15-01-2025") == "15-01-2025"

    def test_parse_date_no_match(self):
        """No date in text should return None."""
        from app.external.tesseract import _parse_date
        assert _parse_date("No dates here") is None

    def test_parse_vendor_first_line(self):
        """Vendor name should be first meaningful capitalized line."""
        from app.external.tesseract import _parse_vendor
        text = "Mumbai Restaurant\nDate: 15/01/2025\nTotal: ₹500"
        assert _parse_vendor(text) == "Mumbai Restaurant"

    def test_parse_vendor_skips_numerics(self):
        """All-numeric lines should be skipped."""
        from app.external.tesseract import _parse_vendor
        text = "12345\nCafe Mocha\nTotal: ₹300"
        assert _parse_vendor(text) == "Cafe Mocha"

    def test_parse_vendor_skips_receipt_fields(self):
        """Lines starting with Date/Total/Tax should be skipped."""
        from app.external.tesseract import _parse_vendor
        text = "Date: 15/01/2025\nTax: 18%\nStarbucks"
        assert _parse_vendor(text) == "Starbucks"

    def test_parse_vendor_none_if_empty(self):
        """Empty text should return None."""
        from app.external.tesseract import _parse_vendor
        assert _parse_vendor("") is None

    def test_parse_gstin_valid(self):
        """Valid GSTIN should be extracted."""
        from app.external.tesseract import _parse_gstin
        text = "GSTIN: 27AAPFU0939F1ZV"
        assert _parse_gstin(text) == "27AAPFU0939F1ZV"

    def test_parse_gstin_embedded(self):
        """GSTIN embedded in text should be extracted."""
        from app.external.tesseract import _parse_gstin
        text = "Invoice No: 123\nGST No 29ABCDE1234F1Z5\nDate: 15/01/2025"
        assert _parse_gstin(text) == "29ABCDE1234F1Z5"

    def test_parse_gstin_no_match(self):
        """No GSTIN in text should return None."""
        from app.external.tesseract import _parse_gstin
        assert _parse_gstin("No GSTIN here 12345") is None

    @patch("app.external.tesseract.pytesseract.image_to_string")
    @patch("app.external.tesseract.Image")
    def test_full_extraction(self, mock_image, mock_ocr):
        """Full OCR extraction with mocked pytesseract."""
        mock_ocr.return_value = (
            "Starbucks Coffee\n"
            "GSTIN: 27AAPFU0939F1ZV\n"
            "Date: 15/01/2025\n"
            "Coffee           ₹250.00\n"
            "CGST 9%          ₹22.50\n"
            "SGST 9%          ₹22.50\n"
            "Total:           ₹295.00\n"
        )
        mock_image.open.return_value = MagicMock()

        from app.external.tesseract import extract_text_from_image_bytes
        result = extract_text_from_image_bytes(b"fake-image-bytes")

        assert result.parsed_amount == Decimal("295.00")
        assert result.parsed_date == "15/01/2025"
        assert result.parsed_vendor == "Starbucks Coffee"
        assert result.parsed_gstin == "27AAPFU0939F1ZV"
        assert result.confidence == Decimal("1")  # 4/4 fields parsed
