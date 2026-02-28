"""Climate platform for the HA Volkswagen integration (EV climatization)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from carconnectivity.climatization import Climatization
from carconnectivity_connectors.volkswagen_na.vehicle import (
    VolkswagenNAElectricVehicle,
    VolkswagenNAHybridVehicle,
)

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature

from .const import DOMAIN
from .entity import VolkswagenBaseEntity

if TYPE_CHECKING:
    from carconnectivity.vehicle import GenericVehicle

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import VolkswagenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_CLIMATIZATION_COMMAND_KEY = "start-stop"

# ClimatizationState values that mean climatization is active
_ACTIVE_STATES = {
    Climatization.ClimatizationState.HEATING,
    Climatization.ClimatizationState.COOLING,
    Climatization.ClimatizationState.VENTILATION,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Volkswagen climate entities (EV / hybrid only)."""
    coordinator: VolkswagenDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        VolkswagenClimate(coordinator, vehicle)
        for vehicle in coordinator.get_vehicles()
        if isinstance(vehicle, (VolkswagenNAElectricVehicle, VolkswagenNAHybridVehicle))
    )


class VolkswagenClimate(VolkswagenBaseEntity, ClimateEntity):
    """Climate entity for Volkswagen EV/hybrid climatization."""

    _attr_name = "Climatization"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 15.5
    _attr_max_temp = 29.5
    _attr_target_temperature_step = 0.5

    def __init__(
        self,
        coordinator: VolkswagenDataUpdateCoordinator,
        vehicle: GenericVehicle,
    ) -> None:
        """Initialise the climate entity."""
        super().__init__(coordinator, vehicle)
        self._attr_unique_id = f"{vehicle.vin.value}_climatization"

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        clim = self._vehicle.climatization
        if not clim.state.enabled:
            return HVACMode.OFF
        if clim.state.value in _ACTIVE_STATES:
            return HVACMode.AUTO
        return HVACMode.OFF

    @property
    def current_temperature(self) -> float | None:
        """Return outside temperature as a proxy for cabin ambient."""
        temp = self._vehicle.outside_temperature
        return temp.value if temp.enabled else None

    @property
    def target_temperature(self) -> float | None:
        """Return the climatization target temperature."""
        settings = self._vehicle.climatization.settings
        if settings and settings.target_temperature.enabled:
            return settings.target_temperature.value
        return None

    def _send_climatization_command(
        self, command: str, target_temp: float | None = None
    ) -> None:
        """Send climatization start/stop command. Runs in executor thread."""
        clim = self._vehicle.climatization
        cmd_obj = clim.commands.get_command(_CLIMATIZATION_COMMAND_KEY)
        if cmd_obj is None:
            raise RuntimeError(
                f"Climatization command not available for vehicle {self._vehicle.vin.value}"
            )
        payload: dict[str, Any] = {"command": command}
        if target_temp is not None:
            payload["target_temperature"] = target_temp
            payload["target_temperature_unit"] = "celsius"
        cmd_obj.value = payload

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode (start or stop climatization)."""
        if hvac_mode == HVACMode.OFF:
            await self.hass.async_add_executor_job(
                self._send_climatization_command, "stop"
            )
        else:
            target = self.target_temperature
            await self.hass.async_add_executor_job(
                self._send_climatization_command, "start", target
            )
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature (starts climatization if off)."""
        temp = kwargs.get("temperature")
        if temp is None:
            return
        await self.hass.async_add_executor_job(
            self._send_climatization_command, "start", temp
        )
        await self.coordinator.async_request_refresh()
