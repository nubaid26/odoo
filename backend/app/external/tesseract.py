# backend/app/external/tesseract.py
"""
Local Tesseract 5 OCR extraction — no network call, no external API, no API key.
Uses pytesseract wrapping the Tesseract binary installed in the Docker image.
"""

from __future__ import annotations

import io
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Optional

import pytesseract
from PIL import Image

from app.config import settings
from app.domain.models import OCRResult

logger = logging.getLogger("trustflow.external.tesseract")

# Configure pytesseract to use the correct binary path
pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

# ── Parsing patterns ──────────────────────────────────────
# Amount patterns: ₹, Rs., INR, $, USD, EUR followed by digits
AMOUNT_PATTERN = re.compile(
    r"(?:₹|Rs\.?|INR|USD|\$|EUR|£)\s*([\d,]+\.?\d*)|"
    r"([\d,]+\.?\d*)\s*(?:₹|Rs\.?|INR|USD|\$|EUR|£)|"
    r"(?:Total|Amount|Grand\s*Total|Net\s*Amount)[:\s]*([\d,]+\.?\d*)",
    re.IGNORECASE,
)

# Date patterns: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, DD.MM.YYYY
DATE_PATTERN = re.compile(
    r"(\d{2}[/\-.]\d{2}[/\-.]\d{4})|"
    r"(\d{4}[/\-.]\d{2}[/\-.]\d{2})"
)

# GSTIN: 15-char alphanumeric matching Indian GST identification format
GSTIN_PATTERN = re.compile(
    r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b"
)


def extract_text_from_image_bytes(image_bytes: bytes) -> OCRResult:
    """
    Extract text from an image using local Tesseract 5.

    Opens image from bytes, runs pytesseract.image_to_string(),
    then parses the raw text to extract amount, date, vendor name, and GSTIN.

    This is a pure local function — no network call, no external API, no API key.

    Args:
        image_bytes: Raw image bytes (JPEG, PNG, etc.)

    Returns:
        OCRResult with raw text and all parsed fields.
    """
    try:
        # Open image from bytes
        image = Image.open(io.BytesIO(image_bytes))

        # Run Tesseract OCR
        raw_text = pytesseract.image_to_string(image, lang="eng")
        logger.info("OCR extracted %d characters of text", len(raw_text))

        # Parse individual fields
        parsed_amount = _parse_amount(raw_text)
        parsed_date = _parse_date(raw_text)
        parsed_vendor = _parse_vendor(raw_text)
        parsed_gstin = _parse_gstin(raw_text)

        # Compute confidence as ratio of parsed fields to expected fields (4 total)
        expected_fields = 4
        parsed_count = sum([
            parsed_amount is not None,
            parsed_date is not None,
            parsed_vendor is not None,
            parsed_gstin is not None,
        ])
        confidence = Decimal(str(parsed_count)) / Decimal(str(expected_fields))

        result = OCRResult(
            raw_text=raw_text,
            parsed_amount=parsed_amount,
            parsed_date=parsed_date,
            parsed_vendor=parsed_vendor,
            parsed_gstin=parsed_gstin,
            confidence=confidence,
        )

        logger.info(
            "OCR result: amount=%s, date=%s, vendor=%s, gstin=%s, confidence=%s",
            parsed_amount, parsed_date, parsed_vendor, parsed_gstin, confidence,
        )
        return result

    except Exception as exc:
        logger.error("OCR extraction failed: %s", exc)
        return OCRResult(
            raw_text="",
            confidence=Decimal("0.0"),
        )


def _parse_amount(text: str) -> Optional[Decimal]:
    """
    Extract the largest monetary amount from OCR text.

    Looks for currency symbols and decimal patterns,
    returns the largest found value as the probable total.
    """
    matches = AMOUNT_PATTERN.findall(text)
    amounts = []
    for groups in matches:
        for group in groups:
            if group:
                try:
                    cleaned = group.replace(",", "").strip()
                    if cleaned:
                        amounts.append(Decimal(cleaned))
                except (InvalidOperation, ValueError):
                    continue

    if amounts:
        # Return the largest amount (most likely the total)
        return max(amounts)
    return None


def _parse_date(text: str) -> Optional[str]:
    """Extract the first date found in OCR text."""
    matches = DATE_PATTERN.findall(text)
    for groups in matches:
        for group in groups:
            if group:
                return group
    return None


def _parse_vendor(text: str) -> Optional[str]:
    """
    Extract vendor name — first non-empty capitalized line before any amount.

    Heuristic: the vendor name is typically the first meaningful line
    in a receipt, before prices appear.
    """
    lines = text.strip().split("\n")
    for line in lines:
        cleaned = line.strip()
        if not cleaned or len(cleaned) < 3:
            continue
        # Skip lines that are purely numeric or look like amounts
        if re.match(r"^[\d\s,.$₹]+$", cleaned):
            continue
        # Skip lines that start with common receipt keywords for non-vendor data
        skip_prefixes = (
            "date", "time", "invoice", "bill", "receipt", "total",
            "tax", "gst", "cgst", "sgst", "amount", "qty", "quantity",
            "item", "sr", "sl", "no.", "#",
        )
        if cleaned.lower().startswith(skip_prefixes):
            continue
        # Return the first plausible vendor line
        return cleaned[:255]

    return None


def _parse_gstin(text: str) -> Optional[str]:
    """Extract GSTIN (15-character alphanumeric) from OCR text."""
    match = GSTIN_PATTERN.search(text.upper())
    if match:
        return match.group(1)
    return None
