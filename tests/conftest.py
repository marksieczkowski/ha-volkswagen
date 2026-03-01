"""Shared test fixtures for the HA Volkswagen integration tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# Enable custom integrations discovery in all tests
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow HA to load custom components from custom_components/ directory."""
    yield


from custom_components.ha_volkswagen.const import (
    CONF_COUNTRY,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SELECTED_VINS,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
)

# ---------------------------------------------------------------------------
# Config entry data
# ---------------------------------------------------------------------------

TEST_USERNAME = "test@example.com"
TEST_PASSWORD = "test-password"
TEST_COUNTRY = "us"
TEST_VIN = "WVWZZZ1JZ3W000001"
TEST_MODEL = "ID.4"

CONFIG_ENTRY_DATA: dict[str, Any] = {
    CONF_USERNAME: TEST_USERNAME,
    CONF_PASSWORD: TEST_PASSWORD,
    CONF_COUNTRY: TEST_COUNTRY,
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    CONF_SELECTED_VINS: [],
}


# ---------------------------------------------------------------------------
# Mock vehicle helpers
# ---------------------------------------------------------------------------


def _make_attr(value: Any, enabled: bool = True) -> MagicMock:
    """Create a mock attribute with .value and .enabled."""
    attr = MagicMock()
    attr.value = value
    attr.enabled = enabled
    return attr


def _make_enum_attr(str_value: str, enabled: bool = True) -> MagicMock:
    """Create a mock enum attribute where .value.value returns the string."""
    inner = MagicMock()
    inner.value = str_value
    return _make_attr(inner, enabled=enabled)


def make_mock_electric_vehicle(
    vin: str = TEST_VIN, model: str = TEST_MODEL
) -> MagicMock:
    """Build a MagicMock shaped like a VolkswagenNAElectricVehicle."""
    vehicle = MagicMock()

    # Identity
    vehicle.vin = _make_attr(vin)
    vehicle.model = _make_attr(model)
    vehicle.model_year = _make_attr(2024)

    # Connection state — online
    vehicle.connection_state = _make_enum_attr("online")

    # Odometer
    vehicle.odometer = _make_attr(12345.0)

    # Outside temperature
    vehicle.outside_temperature = _make_attr(20.0)

    # Doors
    vehicle.doors = MagicMock()
    vehicle.doors.lock_state = _make_enum_attr("locked")
    vehicle.doors.open_state = _make_enum_attr("closed")
    vehicle.doors.doors = {}

    # Windows
    vehicle.windows = MagicMock()
    vehicle.windows.open_state = _make_enum_attr("closed")

    # Lights
    vehicle.lights = MagicMock()
    vehicle.lights.light_state = _make_enum_attr("off")

    # Position
    vehicle.position = MagicMock()
    vehicle.position.latitude = _make_attr(37.7749)
    vehicle.position.longitude = _make_attr(-122.4194)
    vehicle.position.position_type = _make_enum_attr("parking")
    vehicle.position.altitude = _make_attr(None, enabled=False)
    vehicle.position.heading = _make_attr(None, enabled=False)

    # Maintenance
    vehicle.maintenance = MagicMock()
    vehicle.maintenance.inspection_due_at = _make_attr(None, enabled=False)
    vehicle.maintenance.inspection_due_after = _make_attr(None, enabled=False)
    vehicle.maintenance.oil_service_due_at = _make_attr(None, enabled=False)
    vehicle.maintenance.oil_service_due_after = _make_attr(None, enabled=False)

    # Charging (EV)
    vehicle.charging = MagicMock()
    vehicle.charging.state = _make_enum_attr("readyForCharging")
    vehicle.charging.power = _make_attr(11.0)
    vehicle.charging.rate = _make_attr(80.0)
    vehicle.charging.connector = MagicMock()
    vehicle.charging.connector.connection_state = _make_enum_attr("connected")
    vehicle.charging.settings = MagicMock()
    vehicle.charging.settings.target_level = _make_attr(80)
    vehicle.charging.commands = MagicMock()
    mock_charge_cmd = MagicMock()
    vehicle.charging.commands.get_command.return_value = mock_charge_cmd

    # Electric drive (for SOC + range)
    electric_drive = MagicMock()
    electric_drive.level = _make_attr(75.0)
    electric_drive.range = _make_attr(250.0)
    vehicle.get_electric_drive = MagicMock(return_value=electric_drive)
    vehicle.get_combustion_drive = MagicMock(return_value=None)

    # Climatization
    vehicle.climatization = MagicMock()
    vehicle.climatization.state = _make_enum_attr("off")
    vehicle.climatization.settings = MagicMock()
    vehicle.climatization.settings.target_temperature = _make_attr(21.0)
    vehicle.climatization.commands = MagicMock()
    mock_clim_cmd = MagicMock()
    vehicle.climatization.commands.get_command.return_value = mock_clim_cmd

    # Commands (for lock/unlock)
    vehicle.commands = MagicMock()
    mock_lock_cmd = MagicMock()
    vehicle.commands.get_command.return_value = mock_lock_cmd

    return vehicle


def make_mock_garage(vehicles: list | None = None) -> MagicMock:
    """Build a mock Garage containing the given vehicles."""
    if vehicles is None:
        vehicles = [make_mock_electric_vehicle()]
    garage = MagicMock()
    garage.list_vehicles.return_value = vehicles
    return garage


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_electric_vehicle() -> MagicMock:
    """Return a mock electric vehicle."""
    return make_mock_electric_vehicle()


@pytest.fixture
def mock_garage(mock_electric_vehicle: MagicMock) -> MagicMock:
    """Return a mock garage containing one electric vehicle."""
    return make_mock_garage([mock_electric_vehicle])


@pytest.fixture
def mock_carconnectivity(mock_garage: MagicMock):
    """Patch CarConnectivity so no real network calls are made."""
    with patch(
        "custom_components.ha_volkswagen.coordinator.cc.CarConnectivity"
    ) as mock_cls:
        instance = MagicMock()
        instance.get_garage.return_value = mock_garage
        instance.fetch_all = MagicMock()
        instance.persist = MagicMock()
        instance.startup = MagicMock()
        instance.shutdown = MagicMock()
        mock_cls.return_value = instance
        yield instance


@pytest.fixture
def config_entry_data() -> dict[str, Any]:
    """Return standard config entry data."""
    return dict(CONFIG_ENTRY_DATA)
