"""Tests for the Volkswagen charging switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ha_volkswagen.switch import VolkswagenChargingSwitch

from .conftest import _make_attr, _make_enum_attr, make_mock_electric_vehicle


def _make_switch(vehicle) -> VolkswagenChargingSwitch:
    """Construct a VolkswagenChargingSwitch without a real HA setup."""
    coordinator = MagicMock()
    coordinator.data = MagicMock()
    switch = VolkswagenChargingSwitch.__new__(VolkswagenChargingSwitch)
    switch._vehicle = vehicle
    switch.coordinator = coordinator
    switch.hass = MagicMock()
    switch.hass.async_add_executor_job = AsyncMock(
        side_effect=lambda fn, *args: fn(*args)
    )
    coordinator.async_refresh_after_command = AsyncMock()
    return switch


# ---------------------------------------------------------------------------
# is_on — charging active states
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("state_str", "expected"),
    [
        ("charging", True),
        ("readyForCharging", True),
        ("chargingHVBattery", True),
        ("conservation", True),
        ("chargePurposeReachedAndNotConservationCharging", True),
        ("off", False),
        ("discharging", False),
        ("error", False),
    ],
)
def test_is_on_for_charging_states(state_str, expected):
    vehicle = make_mock_electric_vehicle()
    vehicle.charging.state = _make_enum_attr(state_str)
    switch = _make_switch(vehicle)
    assert switch.is_on is expected


def test_is_on_returns_none_when_state_disabled():
    vehicle = make_mock_electric_vehicle()
    vehicle.charging.state = _make_attr(None, enabled=False)
    switch = _make_switch(vehicle)
    assert switch.is_on is None


# ---------------------------------------------------------------------------
# async_turn_on / async_turn_off
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_turn_on_sends_start_command_and_refreshes():
    vehicle = make_mock_electric_vehicle()
    mock_cmd = MagicMock()
    vehicle.charging.commands.commands = {"start-stop": mock_cmd}
    switch = _make_switch(vehicle)

    await switch.async_turn_on()

    assert mock_cmd.value == {"command": "start"}
    switch.coordinator.async_refresh_after_command.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_turn_off_sends_stop_command_and_refreshes():
    vehicle = make_mock_electric_vehicle()
    mock_cmd = MagicMock()
    vehicle.charging.commands.commands = {"start-stop": mock_cmd}
    switch = _make_switch(vehicle)

    await switch.async_turn_off()

    assert mock_cmd.value == {"command": "stop"}
    switch.coordinator.async_refresh_after_command.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_turn_on_raises_when_command_missing():
    vehicle = make_mock_electric_vehicle()
    vehicle.charging.commands.commands = {}
    switch = _make_switch(vehicle)

    with pytest.raises(RuntimeError, match="Charging command not available"):
        await switch.async_turn_on()


# ---------------------------------------------------------------------------
# extra_state_attributes
# ---------------------------------------------------------------------------


def test_extra_state_attributes_includes_charging_fields():
    vehicle = make_mock_electric_vehicle()
    vehicle.charging.state = _make_enum_attr("charging")
    vehicle.charging.power = _make_attr(11.0)
    vehicle.charging.rate = _make_attr(80.0)
    vehicle.charging.settings.target_level = _make_attr(80)
    switch = _make_switch(vehicle)
    attrs = switch.extra_state_attributes
    assert attrs["charging_state"] == "charging"
    assert attrs["charge_power_kw"] == 11.0
    assert attrs["charge_rate_kmh"] == 80.0
    assert attrs["target_soc_pct"] == 80


def test_extra_state_attributes_omits_disabled_fields():
    vehicle = make_mock_electric_vehicle()
    vehicle.charging.state = _make_attr(None, enabled=False)
    vehicle.charging.power = _make_attr(None, enabled=False)
    vehicle.charging.rate = _make_attr(None, enabled=False)
    vehicle.charging.settings.target_level = _make_attr(None, enabled=False)
    switch = _make_switch(vehicle)
    assert switch.extra_state_attributes == {}
