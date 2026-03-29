# backend/app/services/maps_service.py
"""
Maps service — wraps Google Maps client with Haversine distance calculation.
Haversine implemented from scratch — no external library.
"""

from __future__ import annotations

import difflib
import logging
import math
from decimal import Decimal
from typing import Optional

from app.config import settings
from app.external.google_maps import geocode_address, nearby_places

logger = logging.getLogger("trustflow.services.maps")


def haversine_distance(
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
) -> float:
    """
    Calculate the Haversine distance between two points in meters.

    Formula:
        a = sin²(Δlat/2) + cos(lat1)·cos(lat2)·sin²(Δlng/2)
        c = 2·atan2(√a, √(1−a))
        d = R·c where R = 6371000 meters

    No external library used — pure math implementation.

    Args:
        lat1, lng1: First point coordinates in degrees.
        lat2, lng2: Second point coordinates in degrees.

    Returns:
        Distance in meters.
    """
    R = 6371000  # Earth radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = R * c

    return d


async def verify_vendor_location(
    vendor_name: str,
    city: str,
    submitted_lat: Decimal,
    submitted_lng: Decimal,
) -> dict:
    """
    Verify vendor location using Google Maps Geocoding + Nearby Search.

    1. Geocode vendor_name + city to get expected lat/lng.
    2. Compare with submitted GPS coords via Haversine.
    3. Search nearby places for vendor name fuzzy match.

    Args:
        vendor_name: Name of the vendor from the expense.
        city: City where the expense was incurred.
        submitted_lat: GPS latitude from the expense submission.
        submitted_lng: GPS longitude from the expense submission.

    Returns:
        Dict with verification results including:
        - vendor_verified: bool
        - distance_meters: float or None
        - gps_mismatch: bool
        - fuzzy_match_ratio: float
        - nearby_match: bool
    """
    result = {
        "vendor_verified": False,
        "distance_meters": None,
        "gps_mismatch": False,
        "fuzzy_match_ratio": 0.0,
        "nearby_match": False,
        "exact_match": False,
    }

    if not vendor_name:
        logger.warning("No vendor name provided — skipping GPS validation")
        return result

    # Step 1: Geocode the vendor address
    geocoded = await geocode_address(vendor_name, city)
    if geocoded:
        # Step 2: Haversine distance check
        distance = haversine_distance(
            float(submitted_lat),
            float(submitted_lng),
            float(geocoded.lat),
            float(geocoded.lng),
        )
        result["distance_meters"] = round(distance, 2)

        threshold = settings.GPS_MISMATCH_THRESHOLD_METERS
        if distance > threshold:
            result["gps_mismatch"] = True
            logger.warning(
                "GPS mismatch for vendor '%s': %.0fm > %dm threshold",
                vendor_name, distance, threshold,
            )
        else:
            result["vendor_verified"] = True

    # Step 3: Nearby Search for vendor presence
    places = await nearby_places(submitted_lat, submitted_lng, vendor_name)
    if places:
        best_ratio = 0.0
        for place in places:
            ratio = difflib.SequenceMatcher(
                None, vendor_name.lower(), place.name.lower()
            ).ratio()
            if ratio > best_ratio:
                best_ratio = ratio

        result["fuzzy_match_ratio"] = round(best_ratio, 3)

        if best_ratio >= 0.85:
            result["exact_match"] = True
            result["nearby_match"] = True
            result["vendor_verified"] = True
        elif best_ratio >= 0.6:
            result["nearby_match"] = True
            result["vendor_verified"] = True

        logger.info(
            "Nearby search for '%s': best match ratio=%.2f",
            vendor_name, best_ratio,
        )

    return result
