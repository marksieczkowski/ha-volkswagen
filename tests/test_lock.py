"""Tests for the Volkswagen lock platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from carconnectivity.doors import Doors

from custom_components.ha_volkswagen.lock import VolkswagenLock, _supports_lock

from .conftest import _make_attr, _make_enum_attr, make_mock_electric_vehicle


def _make_lock(vehicle) -> VolkswagenLock:
    """Construct a VolkswagenLock without a real HA setup."""
    coordinator = MagicMock()
    coordinator.data = MagicMock()
    lock = VolkswagenLock.__new__(VolkswagenLock)
    lock._vehicle = vehicle
    lock.coordinator = coordinator
    lock.hass = MagicMock()
    lock.hass.async_add_executor_job = AsyncMock(
        side_effect=lambda fn, *args: fn(*args)
    )
    coordinator.async_refresh_after_command = AsyncMock()
    return lock


# ---------------------------------------------------------------------------
# _supports_lock
# ---------------------------------------------------------------------------


def test_supports_lock_returns_true_when_command_present():
    vehicle = make_mock_electric_vehicle()
    vehicle.doors.commands.contains_command.return_value = True
    assert _supports_lock(vehicle) is True


def test_supports_lock_returns_false_when_command_absent():
    vehicle = make_mock_electric_vehicle()
    vehicle.doors.commands.contains_command.return_value = False
    assert _supports_lock(vehicle) is False


def test_supports_lock_returns_false_when_doors_none():
    vehicle = make_mock_electric_vehicle()
    vehicle.doors = None
    assert _supports_lock(vehicle) is False


# ---------------------------------------------------------------------------
# is_locked
# ---------------------------------------------------------------------------


def test_is_locked_returns_true_when_locked():
    vehicle = make_mock_electric_vehicle()
    vehicle.doors.lock_state = _make_attr(Doors.LockState.LOCKED)
    lock = _make_lock(vehicle)
    assert lock.is_locked is True


def test_is_locked_returns_false_when_unlocked():
    vehicle = make_mock_electric_vehicle()
    vehicle.doors.lock_state = _make_attr(Doors.LockState.UNLOCKED)
    lock = _make_lock(vehicle)
    assert lock.is_locked is False


def test_is_locked_returns_none_when_disabled():
    vehicle = make_mock_electric_vehicle()
    vehicle.doors.lock_state = _make_attr(Doors.LockState.LOCKED, enabled=False)
    lock = _make_lock(vehicle)
    assert lock.is_locked is None


# ---------------------------------------------------------------------------
# async_lock / async_unlock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_lock_sends_lock_command_and_refreshes():
    vehicle = make_mock_electric_vehicle()
    mock_cmd = MagicMock()
    vehicle.doors.commands.commands = {"lock-unlock": mock_cmd}
    lock = _make_lock(vehicle)

    await lock.async_lock()

    assert mock_cmd.value == {"command": "lock"}
    lock.coordinator.async_refresh_after_command.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_unlock_sends_unlock_command_and_refreshes():
    vehicle = make_mock_electric_vehicle()
    mock_cmd = MagicMock()
    vehicle.doors.commands.commands = {"lock-unlock": mock_cmd}
    lock = _make_lock(vehicle)

    await lock.async_unlock()

    assert mock_cmd.value == {"command": "unlock"}
    lock.coordinator.async_refresh_after_command.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_lock_raises_when_command_missing():
    vehicle = make_mock_electric_vehicle()
    vehicle.doors.commands.commands = {}
    lock = _make_lock(vehicle)

    with pytest.raises(RuntimeError, match="Lock/unlock command not available"):
        await lock.async_lock()


# ---------------------------------------------------------------------------
# extra_state_attributes
# ---------------------------------------------------------------------------


def test_extra_state_attributes_includes_open_state():
    vehicle = make_mock_electric_vehicle()
    vehicle.doors.open_state = _make_enum_attr("closed")
    lock = _make_lock(vehicle)
    attrs = lock.extra_state_attributes
    assert attrs["overall_open_state"] == "closed"


def test_extra_state_attributes_empty_when_open_state_disabled():
    vehicle = make_mock_electric_vehicle()
    vehicle.doors.open_state = _make_attr(None, enabled=False)
    lock = _make_lock(vehicle)
    assert lock.extra_state_attributes == {}
