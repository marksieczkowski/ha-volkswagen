"""Switch platform for the HA Volkswagen integration (EV charging)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from carconnectivity_connectors.volkswagen_na.vehicle import (
    VolkswagenNAElectricVehicle,
    VolkswagenNAHybridVehicle,
)
from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN
from .entity import VolkswagenBaseEntity

if TYPE_CHECKING:
    from carconnectivity.vehicle import GenericVehicle
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import VolkswagenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_CHARGING_COMMAND_KEY = "start-stop"

# String values (from .value on the enum) that mean charging is on/enabled.
# Covers both the base ChargingState strings and VW NA-specific strings.
_CHARGING_STATE_STRINGS = {
    "charging",
    "ready_for_charging",  # base ChargingState.READY_FOR_CHARGING
    "readyforcharging",  # VolkswagenChargingState variant
    "charginghvbattery",  # VolkswagenChargingState.CHARGING
    "conservation",
    "chargepurposereachedandnotconservationcharging",
    "chargepurposereachedandconservation",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Volkswagen charging switch entities (EV / hybrid only)."""
    coordinator: VolkswagenDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        VolkswagenChargingSwitch(coordinator, vehicle)
        for vehicle in coordinator.get_vehicles()
        if isinstance(vehicle, (VolkswagenNAElectricVehicle, VolkswagenNAHybridVehicle))
    )


class VolkswagenChargingSwitch(VolkswagenBaseEntity, SwitchEntity):
    """Switch entity to start/stop EV charging."""

    _attr_name = "Charging"
    _attr_icon = "mdi:ev-station"

    def __init__(
        self,
        coordinator: VolkswagenDataUpdateCoordinator,
        vehicle: GenericVehicle,
    ) -> None:
        """Initialise the charging switch."""
        super().__init__(coordinator, vehicle)
        self._attr_unique_id = f"{vehicle.vin.value}_charging_switch"

    @property
    def is_on(self) -> bool | None:
        """Return True when the vehicle is charging or ready to charge."""
        state_attr = self._vehicle.charging.state
        if not state_attr.enabled:
            return None
        # .value is an enum; .value.value (or str()) gives the canonical string
        state_str = getattr(state_attr.value, "value", str(state_attr.value))
        return state_str.lower().replace("_", "") in {
            s.replace("_", "") for s in _CHARGING_STATE_STRINGS
        }

    def _send_charging_command(self, command: str) -> None:
        """Send charge start/stop command. Runs in executor thread."""
        cmd_obj = self._vehicle.charging.commands.get_command(_CHARGING_COMMAND_KEY)
        if cmd_obj is None:
            raise RuntimeError(
                f"Charging command not available for vehicle {self._vehicle.vin.value}"
            )
        cmd_obj.value = {"command": command}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start charging."""
        await self.hass.async_add_executor_job(self._send_charging_command, "start")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop charging."""
        await self.hass.async_add_executor_job(self._send_charging_command, "stop")
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional charging attributes."""
        attrs: dict[str, Any] = {}
        charging = self._vehicle.charging

        if charging.state.enabled:
            attrs["charging_state"] = charging.state.value.value

        if charging.power.enabled:
            attrs["charge_power_kw"] = charging.power.value

        if charging.rate.enabled:
            attrs["charge_rate_kmh"] = charging.rate.value

        target_level = charging.settings.target_level
        if target_level.enabled:
            attrs["target_soc_pct"] = target_level.value

        return attrs
