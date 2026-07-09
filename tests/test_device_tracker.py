"""Tests for the Volkswagen device tracker platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.ha_volkswagen.device_tracker import VolkswagenDeviceTracker

from .conftest import TEST_VIN, _make_attr, make_mock_electric_vehicle


def _make_tracker(vehicle) -> VolkswagenDeviceTracker:
    """Construct a VolkswagenDeviceTracker without a real HA setup."""
    coordinator = MagicMock()
    coordinator.data = MagicMock()
    tracker = VolkswagenDeviceTracker.__new__(VolkswagenDeviceTracker)
    tracker._vehicle = vehicle
    tracker.coordinator = coordinator
    tracker._update_position()
    return tracker


# ---------------------------------------------------------------------------
# latitude / longitude
# ---------------------------------------------------------------------------


def test_latitude_longitude_from_position():
    vehicle = make_mock_electric_vehicle()
    tracker = _make_tracker(vehicle)

    assert tracker.latitude == 37.7749
    assert tracker.longitude == -122.4194


def test_latitude_longitude_none_when_position_missing():
    vehicle = make_mock_electric_vehicle()
    vehicle.position = None
    tracker = _make_tracker(vehicle)

    assert tracker.latitude is None
    assert tracker.longitude is None


def test_latitude_longitude_none_when_disabled():
    vehicle = make_mock_electric_vehicle()
    vehicle.position.latitude = _make_attr(None, enabled=False)
    vehicle.position.longitude = _make_attr(None, enabled=False)
    tracker = _make_tracker(vehicle)

    assert tracker.latitude is None
    assert tracker.longitude is None


# ---------------------------------------------------------------------------
# extra_state_attributes
# ---------------------------------------------------------------------------


def test_extra_state_attributes_with_position_type():
    vehicle = make_mock_electric_vehicle()
    tracker = _make_tracker(vehicle)

    attrs = tracker.extra_state_attributes
    assert attrs["position_type"] == "parking"
    # lat/long are provided natively by TrackerEntity — must not be duplicated
    assert "latitude" not in attrs
    assert "longitude" not in attrs
    # altitude/heading are disabled in the default mock
    assert "altitude_m" not in attrs
    assert "heading_deg" not in attrs


def test_extra_state_attributes_with_altitude_and_heading():
    vehicle = make_mock_electric_vehicle()
    vehicle.position.altitude = _make_attr(12.5)
    vehicle.position.heading = _make_attr(270)
    tracker = _make_tracker(vehicle)

    attrs = tracker.extra_state_attributes
    assert attrs["altitude_m"] == 12.5
    assert attrs["heading_deg"] == 270


def test_extra_state_attributes_empty_when_position_missing():
    vehicle = make_mock_electric_vehicle()
    vehicle.position = None
    tracker = _make_tracker(vehicle)

    assert tracker.extra_state_attributes == {}


# ---------------------------------------------------------------------------
# entity identity
# ---------------------------------------------------------------------------


def test_unique_id_and_name():
    vehicle = make_mock_electric_vehicle()
    tracker = VolkswagenDeviceTracker(MagicMock(), vehicle)

    assert tracker.unique_id == f"{TEST_VIN}_position"
    assert tracker._attr_name == "Location"
