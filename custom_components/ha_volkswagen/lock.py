"""Lock platform for the HA Volkswagen integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from carconnectivity.doors import Doors
from homeassistant.components.lock import LockEntity

from .const import DOMAIN
from .entity import VolkswagenBaseEntity

if TYPE_CHECKING:
    from carconnectivity.vehicle import GenericVehicle
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import VolkswagenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Command key as registered by the carconnectivity NA connector
_LOCK_UNLOCK_COMMAND_KEY = "lock-unlock"


def _supports_lock(vehicle: GenericVehicle) -> bool:
    """Return True if the vehicle supports remote lock/unlock."""
    return (
        vehicle.doors is not None
        and vehicle.doors.commands is not None
        and vehicle.doors.commands.contains_command(_LOCK_UNLOCK_COMMAND_KEY)
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Volkswagen lock entities."""
    coordinator: VolkswagenDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        VolkswagenLock(coordinator, vehicle)
        for vehicle in coordinator.get_vehicles()
        if _supports_lock(vehicle)
    )


class VolkswagenLock(VolkswagenBaseEntity, LockEntity):
    """Lock entity controlling Volkswagen door lock/unlock."""

    _attr_name = "Doors"

    def __init__(
        self,
        coordinator: VolkswagenDataUpdateCoordinator,
        vehicle: GenericVehicle,
    ) -> None:
        """Initialise the lock."""
        super().__init__(coordinator, vehicle)
        self._attr_unique_id = f"{vehicle.vin.value}_lock"

    @property
    def is_locked(self) -> bool | None:
        """Return True when all doors are locked."""
        lock_state = self._vehicle.doors.lock_state
        if not lock_state.enabled:
            return None
        return lock_state.value == Doors.LockState.LOCKED

    def _send_lock_command(self, command: str) -> None:
        """Send a lock or unlock command. Runs in executor thread."""
        cmd_obj = self._vehicle.doors.commands.commands.get(_LOCK_UNLOCK_COMMAND_KEY)
        if cmd_obj is None:
            vin = self._vehicle.vin.value
            raise RuntimeError(f"Lock/unlock command not available for vehicle {vin}")
        cmd_obj.value = {"command": command}

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the vehicle doors."""
        await self.hass.async_add_executor_job(self._send_lock_command, "lock")
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the vehicle doors."""
        await self.hass.async_add_executor_job(self._send_lock_command, "unlock")
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {}
        doors = self._vehicle.doors
        if doors.open_state.enabled:
            attrs["overall_open_state"] = doors.open_state.value.value
        return attrs
