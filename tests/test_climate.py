"""Tests for the Volkswagen climate platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from carconnectivity.climatization import Climatization
from carconnectivity.units import Temperature
from homeassistant.components.climate import HVACMode
from homeassistant.const import UnitOfTemperature

from custom_components.ha_volkswagen.climate import VolkswagenClimate

from .conftest import _make_attr, make_mock_electric_vehicle


def _make_climate(vehicle, use_fahrenheit: bool = False) -> VolkswagenClimate:
    """Construct a VolkswagenClimate without a real HA setup."""
    coordinator = MagicMock()
    coordinator.data = MagicMock()
    climate = VolkswagenClimate.__new__(VolkswagenClimate)
    climate._vehicle = vehicle
    climate.coordinator = coordinator
    climate.hass = MagicMock()
    climate.hass.config.units.temperature_unit = (
        UnitOfTemperature.FAHRENHEIT if use_fahrenheit else UnitOfTemperature.CELSIUS
    )
    climate.hass.async_add_executor_job = AsyncMock(
        side_effect=lambda fn, *args: fn(*args)
    )
    coordinator.async_refresh_after_command = AsyncMock()
    return climate


# ---------------------------------------------------------------------------
# hvac_mode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("state", "expected_mode"),
    [
        (Climatization.ClimatizationState.HEATING, HVACMode.AUTO),
        (Climatization.ClimatizationState.COOLING, HVACMode.AUTO),
        (Climatization.ClimatizationState.VENTILATION, HVACMode.AUTO),
        (Climatization.ClimatizationState.OFF, HVACMode.OFF),
    ],
)
def test_hvac_mode(state, expected_mode):
    vehicle = make_mock_electric_vehicle()
    vehicle.climatization.state = _make_attr(state)
    climate = _make_climate(vehicle)
    assert climate.hvac_mode is expected_mode


def test_hvac_mode_off_when_state_disabled():
    vehicle = make_mock_electric_vehicle()
    vehicle.climatization.state = _make_attr(None, enabled=False)
    climate = _make_climate(vehicle)
    assert climate.hvac_mode is HVACMode.OFF


# ---------------------------------------------------------------------------
# target_temperature
# ---------------------------------------------------------------------------


def test_target_temperature_celsius():
    vehicle = make_mock_electric_vehicle()
    temp_attr = MagicMock()
    temp_attr.enabled = True
    temp_attr.temperature_in.return_value = 21.5
    vehicle.climatization.settings.target_temperature = temp_attr
    climate = _make_climate(vehicle, use_fahrenheit=False)
    assert climate.target_temperature == 21.5
    temp_attr.temperature_in.assert_called_with(Temperature.C)


def test_target_temperature_fahrenheit():
    vehicle = make_mock_electric_vehicle()
    temp_attr = MagicMock()
    temp_attr.enabled = True
    temp_attr.temperature_in.return_value = 72.0
    vehicle.climatization.settings.target_temperature = temp_attr
    climate = _make_climate(vehicle, use_fahrenheit=True)
    assert climate.target_temperature == 72.0
    temp_attr.temperature_in.assert_called_with(Temperature.F)


def test_target_temperature_none_when_disabled():
    vehicle = make_mock_electric_vehicle()
    vehicle.climatization.settings.target_temperature = _make_attr(None, enabled=False)
    climate = _make_climate(vehicle)
    assert climate.target_temperature is None


# ---------------------------------------------------------------------------
# async_set_hvac_mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_set_hvac_mode_off_sends_stop_command():
    vehicle = make_mock_electric_vehicle()
    mock_cmd = MagicMock()
    vehicle.climatization.commands.commands = {"start-stop": mock_cmd}
    climate = _make_climate(vehicle)

    await climate.async_set_hvac_mode(HVACMode.OFF)

    assert mock_cmd.value == {"command": "stop"}
    climate.coordinator.async_refresh_after_command.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_set_hvac_mode_auto_sends_start_command():
    vehicle = make_mock_electric_vehicle()
    mock_cmd = MagicMock()
    vehicle.climatization.commands.commands = {"start-stop": mock_cmd}
    temp_attr = MagicMock()
    temp_attr.enabled = True
    temp_attr.temperature_in.return_value = 21.0
    vehicle.climatization.settings.target_temperature = temp_attr
    climate = _make_climate(vehicle)

    await climate.async_set_hvac_mode(HVACMode.AUTO)

    assert mock_cmd.value == {
        "command": "start",
        "target_temperature": 21.0,
        "target_temperature_unit": "celsius",
    }
    climate.coordinator.async_refresh_after_command.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_set_hvac_mode_raises_when_command_missing():
    vehicle = make_mock_electric_vehicle()
    vehicle.climatization.commands.commands = {}
    climate = _make_climate(vehicle)

    with pytest.raises(RuntimeError, match="Climatization command not available"):
        await climate.async_set_hvac_mode(HVACMode.OFF)


# ---------------------------------------------------------------------------
# async_set_temperature
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_set_temperature_celsius_sends_start_command():
    vehicle = make_mock_electric_vehicle()
    mock_cmd = MagicMock()
    vehicle.climatization.commands.commands = {"start-stop": mock_cmd}
    climate = _make_climate(vehicle, use_fahrenheit=False)

    await climate.async_set_temperature(temperature=22.0)

    assert mock_cmd.value == {
        "command": "start",
        "target_temperature": 22.0,
        "target_temperature_unit": "celsius",
    }
    climate.coordinator.async_refresh_after_command.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_set_temperature_fahrenheit_converts_to_celsius():
    vehicle = make_mock_electric_vehicle()
    mock_cmd = MagicMock()
    vehicle.climatization.commands.commands = {"start-stop": mock_cmd}
    climate = _make_climate(vehicle, use_fahrenheit=True)

    await climate.async_set_temperature(temperature=72.0)  # 72°F → ~22.2°C

    called_payload = mock_cmd.value
    assert called_payload["command"] == "start"
    assert called_payload["target_temperature_unit"] == "celsius"
    assert abs(called_payload["target_temperature"] - 22.22) < 0.1


@pytest.mark.asyncio
async def test_async_set_temperature_noop_when_no_temp():
    vehicle = make_mock_electric_vehicle()
    climate = _make_climate(vehicle)

    await climate.async_set_temperature()  # no temperature kwarg

    climate.coordinator.async_refresh_after_command.assert_not_awaited()
