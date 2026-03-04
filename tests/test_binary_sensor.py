"""Tests for the Volkswagen binary sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from carconnectivity.windows import Windows

from custom_components.ha_volkswagen.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    VolkswagenBinarySensor,
    _window_open,
)

from .conftest import (
    _make_attr,
    make_mock_electric_vehicle,
    make_mock_garage,
)


def _get_description(key: str):
    """Return the BinarySensorEntityDescription with the given key."""
    for desc in BINARY_SENSOR_DESCRIPTIONS:
        if desc.key == key:
            return desc
    raise KeyError(f"No binary sensor description with key {key!r}")


def _make_binary_sensor(vehicle, key: str) -> VolkswagenBinarySensor:
    """Construct a VolkswagenBinarySensor without a real HA coordinator."""
    description = _get_description(key)
    coordinator = MagicMock()
    coordinator.data = make_mock_garage([vehicle])
    sensor = VolkswagenBinarySensor.__new__(VolkswagenBinarySensor)
    sensor._vehicle = vehicle
    sensor.entity_description = description
    sensor.coordinator = coordinator
    return sensor


def _make_window(open_state_value, enabled: bool = True) -> MagicMock:
    """Create a mock window with open_state."""
    window = MagicMock()
    window.open_state = _make_attr(open_state_value, enabled=enabled)
    return window


# ---------------------------------------------------------------------------
# Individual window helper
# ---------------------------------------------------------------------------


def test_window_open_returns_true_when_open():
    vehicle = make_mock_electric_vehicle()
    vehicle.windows.windows = {"frontLeft": _make_window(Windows.OpenState.OPEN)}
    assert _window_open(vehicle, "frontLeft") is True


def test_window_open_returns_true_when_ajar():
    vehicle = make_mock_electric_vehicle()
    vehicle.windows.windows = {"frontLeft": _make_window(Windows.OpenState.AJAR)}
    assert _window_open(vehicle, "frontLeft") is True


def test_window_open_returns_false_when_closed():
    vehicle = make_mock_electric_vehicle()
    vehicle.windows.windows = {"frontLeft": _make_window(Windows.OpenState.CLOSED)}
    assert _window_open(vehicle, "frontLeft") is False


def test_window_open_returns_none_when_disabled():
    vehicle = make_mock_electric_vehicle()
    vehicle.windows.windows = {
        "frontLeft": _make_window(Windows.OpenState.OPEN, enabled=False)
    }
    assert _window_open(vehicle, "frontLeft") is None


def test_window_open_returns_none_when_key_missing():
    vehicle = make_mock_electric_vehicle()
    vehicle.windows.windows = {}
    assert _window_open(vehicle, "frontLeft") is None


# ---------------------------------------------------------------------------
# Individual window binary sensors
# ---------------------------------------------------------------------------


def test_window_front_left_open():
    vehicle = make_mock_electric_vehicle()
    vehicle.windows.windows = {"frontLeft": _make_window(Windows.OpenState.OPEN)}
    sensor = _make_binary_sensor(vehicle, "window_front_left")
    assert sensor.is_on is True


def test_window_front_right_closed():
    vehicle = make_mock_electric_vehicle()
    vehicle.windows.windows = {"frontRight": _make_window(Windows.OpenState.CLOSED)}
    sensor = _make_binary_sensor(vehicle, "window_front_right")
    assert sensor.is_on is False


def test_window_rear_left_missing_returns_none():
    vehicle = make_mock_electric_vehicle()
    vehicle.windows.windows = {}
    sensor = _make_binary_sensor(vehicle, "window_rear_left")
    assert sensor.is_on is None


def test_window_rear_right_ajar_is_on():
    vehicle = make_mock_electric_vehicle()
    vehicle.windows.windows = {"rearRight": _make_window(Windows.OpenState.AJAR)}
    sensor = _make_binary_sensor(vehicle, "window_rear_right")
    assert sensor.is_on is True
