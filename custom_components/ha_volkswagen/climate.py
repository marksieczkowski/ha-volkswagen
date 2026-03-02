"""Climate platform for the HA Volkswagen integration (EV climatization)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from carconnectivity.climatization import Climatization
from carconnectivity.units import Temperature
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

_CLIM_MIN_CELSIUS = 15.5
_CLIM_MAX_CELSIUS = 29.5

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

    def __init__(
        self,
        coordinator: VolkswagenDataUpdateCoordinator,
        vehicle: GenericVehicle,
    ) -> None:
        """Initialise the climate entity."""
        super().__init__(coordinator, vehicle)
        self._attr_unique_id = f"{vehicle.vin.value}_climatization"

    @property
    def _use_fahrenheit(self) -> bool:
        """Return True if HA is configured to use Fahrenheit."""
        return self.hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT

    @property
    def temperature_unit(self) -> str:
        """Return the temperature unit matching HA's configured unit system."""
        return self.hass.config.units.temperature_unit

    @property
    def min_temp(self) -> float:
        """Return minimum climatization temperature."""
        if self._use_fahrenheit:
            return round(_CLIM_MIN_CELSIUS * 9 / 5 + 32)  # 60°F
        return _CLIM_MIN_CELSIUS

    @property
    def max_temp(self) -> float:
        """Return maximum climatization temperature."""
        if self._use_fahrenheit:
            return round(_CLIM_MAX_CELSIUS * 9 / 5 + 32)  # 85°F
        return _CLIM_MAX_CELSIUS

    @property
    def target_temperature_step(self) -> float:
        """Return temperature step (1°F or 0.5°C)."""
        return 1.0 if self._use_fahrenheit else 0.5

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
        if not temp.enabled:
            return None
        target_unit = Temperature.F if self._use_fahrenheit else Temperature.C
        val = temp.temperature_in(target_unit)
        return round(val, 1) if val is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the climatization target temperature."""
        settings = self._vehicle.climatization.settings
        if not (settings and settings.target_temperature.enabled):
            return None
        target_unit = Temperature.F if self._use_fahrenheit else Temperature.C
        val = settings.target_temperature.temperature_in(target_unit)
        return round(val, 1) if val is not None else None

    def _send_climatization_command(
        self, command: str, target_temp: float | None = None
    ) -> None:
        """Send climatization start/stop command. Runs in executor thread."""
        clim = self._vehicle.climatization
        cmd_obj = clim.commands.get_command(_CLIMATIZATION_COMMAND_KEY)
        if cmd_obj is None:
            vin = self._vehicle.vin.value
            raise RuntimeError(f"Climatization command not available for vehicle {vin}")
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
            # Read target temp in Celsius for the API command.
            # Use temperature_in(Temperature.C) to handle the case where the library
            # stores the value in Fahrenheit (as VW NA does for NA vehicles).
            settings = self._vehicle.climatization.settings
            target_celsius = (
                settings.target_temperature.temperature_in(Temperature.C)
                if settings and settings.target_temperature.enabled
                else None
            )
            await self.hass.async_add_executor_job(
                self._send_climatization_command, "start", target_celsius
            )
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature (starts climatization if off)."""
        temp = kwargs.get("temperature")
        if temp is None:
            return
        if self._use_fahrenheit:
            temp = (temp - 32) * 5 / 9  # convert °F → °C for the API
        await self.hass.async_add_executor_job(
            self._send_climatization_command, "start", temp
        )
        await self.coordinator.async_request_refresh()
