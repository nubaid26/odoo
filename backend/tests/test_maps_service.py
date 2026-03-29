# backend/tests/test_maps_service.py
"""
Maps service tests — Haversine distance formula and vendor verification logic.
Google Maps API calls are mocked.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.services.maps_service import haversine_distance, verify_vendor_location
from app.domain.models import GeoLocation, NearbyPlace


class TestHaversineDistance:
    """Test the from-scratch Haversine implementation."""

    def test_same_point_is_zero(self):
        """Same coordinates should return 0 meters."""
        dist = haversine_distance(19.076, 72.877, 19.076, 72.877)
        assert dist == 0.0

    def test_known_distance_mumbai_to_delhi(self):
        """Mumbai (19.076, 72.877) to Delhi (28.613, 77.209): ~1153 km."""
        dist = haversine_distance(19.076, 72.877, 28.613, 77.209)
        km = dist / 1000
        assert 1100 < km < 1200, f"Expected ~1153km, got {km:.0f}km"

    def test_short_distance(self):
        """Two nearby points in Mumbai: ~1km apart."""
        dist = haversine_distance(19.076, 72.877, 19.085, 72.883)
        assert 500 < dist < 2000, f"Expected ~1km, got {dist:.0f}m"

    def test_antipodal_points(self):
        """Diametrically opposite points: ~20000km."""
        dist = haversine_distance(0, 0, 0, 180)
        km = dist / 1000
        assert 19900 < km < 20100, f"Expected ~20000km, got {km:.0f}km"

    def test_equator_one_degree_longitude(self):
        """1 degree longitude at equator: ~111.3km."""
        dist = haversine_distance(0, 0, 0, 1)
        km = dist / 1000
        assert 110 < km < 113, f"Expected ~111km, got {km:.1f}km"

    def test_symmetry(self):
        """Distance A→B should equal distance B→A."""
        d1 = haversine_distance(19.076, 72.877, 28.613, 77.209)
        d2 = haversine_distance(28.613, 77.209, 19.076, 72.877)
        assert abs(d1 - d2) < 0.01


class TestVerifyVendorLocation:
    """Test vendor location verification with mocked Google Maps."""

    @pytest.mark.asyncio
    async def test_no_vendor_name_returns_unverified(self):
        """Empty vendor name should return unverified result."""
        result = await verify_vendor_location(
            vendor_name="",
            city="Mumbai",
            submitted_lat=Decimal("19.076"),
            submitted_lng=Decimal("72.877"),
        )
        assert result["vendor_verified"] is False

    @pytest.mark.asyncio
    @patch("app.services.maps_service.geocode_address")
    @patch("app.services.maps_service.nearby_places")
    async def test_exact_match_verifies(self, mock_nearby, mock_geocode):
        """Exact nearby match should verify vendor."""
        mock_geocode.return_value = GeoLocation(lat=Decimal("19.076"), lng=Decimal("72.877"))
        mock_nearby.return_value = [
            NearbyPlace(name="Starbucks Coffee", vicinity="Andheri", place_id="abc123"),
        ]

        result = await verify_vendor_location(
            vendor_name="Starbucks Coffee",
            city="Mumbai",
            submitted_lat=Decimal("19.076"),
            submitted_lng=Decimal("72.877"),
        )
        assert result["vendor_verified"] is True
        assert result["fuzzy_match_ratio"] >= 0.85

    @pytest.mark.asyncio
    @patch("app.services.maps_service.geocode_address")
    @patch("app.services.maps_service.nearby_places")
    async def test_gps_mismatch_detected(self, mock_nearby, mock_geocode):
        """Large distance mismatch should flag GPS mismatch."""
        # Geocoded location 100km away
        mock_geocode.return_value = GeoLocation(lat=Decimal("28.613"), lng=Decimal("77.209"))
        mock_nearby.return_value = []

        result = await verify_vendor_location(
            vendor_name="Test Vendor",
            city="Delhi",
            submitted_lat=Decimal("19.076"),
            submitted_lng=Decimal("72.877"),
        )
        assert result["gps_mismatch"] is True
        assert result["distance_meters"] > 1000000  # > 1000km

    @pytest.mark.asyncio
    @patch("app.services.maps_service.geocode_address")
    @patch("app.services.maps_service.nearby_places")
    async def test_fuzzy_match_verifies(self, mock_nearby, mock_geocode):
        """Fuzzy vendor name match >= 0.6 should verify."""
        mock_geocode.return_value = None
        mock_nearby.return_value = [
            NearbyPlace(name="Cafe Mocha Mumbai", vicinity="Bandra", place_id="def456"),
        ]

        result = await verify_vendor_location(
            vendor_name="Cafe Mocha",
            city="Mumbai",
            submitted_lat=Decimal("19.076"),
            submitted_lng=Decimal("72.877"),
        )
        assert result["nearby_match"] is True
        assert result["vendor_verified"] is True
        assert result["fuzzy_match_ratio"] >= 0.6

    @pytest.mark.asyncio
    @patch("app.services.maps_service.geocode_address")
    @patch("app.services.maps_service.nearby_places")
    async def test_no_match_unverified(self, mock_nearby, mock_geocode):
        """No geocode and no nearby match should be unverified."""
        mock_geocode.return_value = None
        mock_nearby.return_value = []

        result = await verify_vendor_location(
            vendor_name="Unknown Vendor XYZ",
            city="Mumbai",
            submitted_lat=Decimal("19.076"),
            submitted_lng=Decimal("72.877"),
        )
        assert result["vendor_verified"] is False
        assert result["nearby_match"] is False
