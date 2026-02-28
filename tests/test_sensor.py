"""Tests for the Volkswagen sensor platform."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.ha_volkswagen.sensor import (
    SENSOR_DESCRIPTIONS,
    VolkswagenSensor,
)

from .conftest import (
    _make_attr,
    _make_enum_attr,
    make_mock_electric_vehicle,
    make_mock_garage,
)


def _get_description(key: str):
    """Return the SensorEntityDescription with the given key."""
    for desc in SENSOR_DESCRIPTIONS:
        if desc.key == key:
            return desc
    raise KeyError(f"No sensor description with key {key!r}")


def _make_sensor(vehicle, key: str, coordinator=None) -> VolkswagenSensor:
    """Construct a VolkswagenSensor without a real HA coordinator."""
    description = _get_description(key)
    if coordinator is None:
        coordinator = MagicMock()
        coordinator.data = make_mock_garage([vehicle])
    sensor = VolkswagenSensor.__new__(VolkswagenSensor)
    sensor._vehicle = vehicle
    sensor.entity_description = description
    sensor.coordinator = coordinator
    return sensor


# ---------------------------------------------------------------------------
# Odometer
# ---------------------------------------------------------------------------

def test_odometer_returns_value():
    vehicle = make_mock_electric_vehicle()
    vehicle.odometer = _make_attr(12345.0)
    sensor = _make_sensor(vehicle, "odometer")
    assert sensor.native_value == 12345.0


def test_odometer_returns_none_when_disabled():
    vehicle = make_mock_electric_vehicle()
    vehicle.odometer = _make_attr(None, enabled=False)
    sensor = _make_sensor(vehicle, "odometer")
    assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Battery SoC
# ---------------------------------------------------------------------------

def test_battery_soc_returns_value():
    vehicle = make_mock_electric_vehicle()
    electric_drive = MagicMock()
    electric_drive.level = _make_attr(80.0)
    vehicle.get_electric_drive.return_value = electric_drive
    sensor = _make_sensor(vehicle, "battery_soc")
    assert sensor.native_value == 80.0


def test_battery_soc_returns_none_when_drive_disabled():
    vehicle = make_mock_electric_vehicle()
    electric_drive = MagicMock()
    electric_drive.level = _make_attr(None, enabled=False)
    vehicle.get_electric_drive.return_value = electric_drive
    sensor = _make_sensor(vehicle, "battery_soc")
    assert sensor.native_value is None


def test_battery_soc_returns_none_when_no_electric_drive():
    vehicle = make_mock_electric_vehicle()
    vehicle.get_electric_drive.return_value = None
    sensor = _make_sensor(vehicle, "battery_soc")
    assert sensor.native_value is None


# ---------------------------------------------------------------------------
# EV Range
# ---------------------------------------------------------------------------

def test_ev_range_returns_value():
    vehicle = make_mock_electric_vehicle()
    electric_drive = MagicMock()
    electric_drive.range = _make_attr(300.0)
    vehicle.get_electric_drive.return_value = electric_drive
    sensor = _make_sensor(vehicle, "ev_range")
    assert sensor.native_value == 300.0


# ---------------------------------------------------------------------------
# Outside temperature
# ---------------------------------------------------------------------------

def test_outside_temperature_returns_value():
    vehicle = make_mock_electric_vehicle()
    vehicle.outside_temperature = _make_attr(22.5)
    sensor = _make_sensor(vehicle, "outside_temperature")
    assert sensor.native_value == 22.5


def test_outside_temperature_returns_none_when_disabled():
    vehicle = make_mock_electric_vehicle()
    vehicle.outside_temperature = _make_attr(None, enabled=False)
    sensor = _make_sensor(vehicle, "outside_temperature")
    assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Charging state
# ---------------------------------------------------------------------------

def test_charging_state_returns_enum_string():
    vehicle = make_mock_electric_vehicle()
    vehicle.charging.state = _make_enum_attr("readyForCharging")
    sensor = _make_sensor(vehicle, "charging_state")
    assert sensor.native_value == "readyForCharging"


def test_charging_state_returns_none_when_disabled():
    vehicle = make_mock_electric_vehicle()
    vehicle.charging.state = _make_attr(None, enabled=False)
    sensor = _make_sensor(vehicle, "charging_state")
    assert sensor.native_value is None


# ---------------------------------------------------------------------------
# supported_fn: EV-only sensors must not be added for combustion vehicles
# ---------------------------------------------------------------------------

def test_battery_soc_not_supported_for_combustion():
    """battery_soc should report unsupported for ICE-only vehicles."""
    from carconnectivity_connectors.volkswagen_na.vehicle import VolkswagenNACombustionVehicle

    combustion_vehicle = MagicMock(spec=VolkswagenNACombustionVehicle)
    desc = _get_description("battery_soc")
    assert not desc.supported_fn(combustion_vehicle)


def test_battery_soc_supported_for_electric():
    """battery_soc should report supported for EV vehicles."""
    from carconnectivity_connectors.volkswagen_na.vehicle import VolkswagenNAElectricVehicle

    ev_vehicle = MagicMock(spec=VolkswagenNAElectricVehicle)
    desc = _get_description("battery_soc")
    assert desc.supported_fn(ev_vehicle)


def test_fuel_level_not_supported_for_electric():
    """fuel_level should report unsupported for EV-only vehicles."""
    from carconnectivity_connectors.volkswagen_na.vehicle import VolkswagenNAElectricVehicle

    ev_vehicle = MagicMock(spec=VolkswagenNAElectricVehicle)
    desc = _get_description("fuel_level")
    assert not desc.supported_fn(ev_vehicle)


def test_fuel_level_supported_for_combustion():
    """fuel_level should report supported for combustion vehicles."""
    from carconnectivity_connectors.volkswagen_na.vehicle import VolkswagenNACombustionVehicle

    combustion_vehicle = MagicMock(spec=VolkswagenNACombustionVehicle)
    desc = _get_description("fuel_level")
    assert desc.supported_fn(combustion_vehicle)


# ---------------------------------------------------------------------------
# Odometer is supported for all vehicle types
# ---------------------------------------------------------------------------

def test_odometer_supported_for_all_types():
    """odometer should have a supported_fn that returns True for any vehicle."""
    desc = _get_description("odometer")
    assert desc.supported_fn(MagicMock())
