"""Climate platform for the HA Volkswagen integration (EV climatization)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from carconnectivity.attributes import TemperatureAttribute
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
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError

from .entity import VolkswagenBaseEntity

if TYPE_CHECKING:
    from carconnectivity.vehicle import GenericVehicle
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import VolkswagenConfigEntry, VolkswagenDataUpdateCoordinator

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
    entry: VolkswagenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Volkswagen climate entities (EV / hybrid only)."""
    coordinator = entry.runtime_data

    async_add_entities(
        VolkswagenClimate(coordinator, vehicle)
        for vehicle in coordinator.get_vehicles()
        if isinstance(vehicle, (VolkswagenNAElectricVehicle, VolkswagenNAHybridVehicle))
    )


class VolkswagenClimate(VolkswagenBaseEntity, ClimateEntity):
    """Climate entity for Volkswagen EV/hybrid climatization."""

    _attr_name = "Climatization"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

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
    def _display_unit(self) -> Temperature:
        """Return HA's configured unit as a carconnectivity Temperature."""
        return Temperature.F if self._use_fahrenheit else Temperature.C

    @property
    def _target_temperature_attr(self) -> TemperatureAttribute | None:
        """Return the climatization target temperature attribute, if present."""
        settings = self._vehicle.climatization.settings
        return settings.target_temperature if settings else None

    @property
    def temperature_unit(self) -> str:
        """Return the temperature unit matching HA's configured unit system."""
        return self.hass.config.units.temperature_unit

    @property
    def min_temp(self) -> float:
        """Return minimum climatization temperature."""
        attr = self._target_temperature_attr
        if (
            attr is not None
            and attr.enabled
            and attr.minimum is not None
            and attr.unit is not None
        ):
            return round(
                TemperatureAttribute.convert(
                    attr.minimum, attr.unit, self._display_unit
                ),
                1,
            )
        if self._use_fahrenheit:
            return round(_CLIM_MIN_CELSIUS * 9 / 5 + 32)  # 60°F
        return _CLIM_MIN_CELSIUS

    @property
    def max_temp(self) -> float:
        """Return maximum climatization temperature."""
        attr = self._target_temperature_attr
        if (
            attr is not None
            and attr.enabled
            and attr.maximum is not None
            and attr.unit is not None
        ):
            return round(
                TemperatureAttribute.convert(
                    attr.maximum, attr.unit, self._display_unit
                ),
                1,
            )
        if self._use_fahrenheit:
            return round(_CLIM_MAX_CELSIUS * 9 / 5 + 32)  # 85°F
        return _CLIM_MAX_CELSIUS

    @property
    def target_temperature_step(self) -> float:
        """Return temperature step (1°F or 0.5°C unless the API says otherwise)."""
        attr = self._target_temperature_attr
        # Precision is a delta, not a point — only usable as-is when the attribute's
        # unit matches the display unit (a °F step converted to °C would be wrong).
        if (
            attr is not None
            and attr.enabled
            and attr.precision is not None
            and attr.unit == self._display_unit
        ):
            return attr.precision
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
        val = temp.temperature_in(self._display_unit)
        return round(val, 1) if val is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the climatization target temperature."""
        attr = self._target_temperature_attr
        if attr is None or not attr.enabled:
            return None
        val = attr.temperature_in(self._display_unit)
        return round(val, 1) if val is not None else None

    def _send_climatization_command(self, command: str) -> None:
        """Send climatization start/stop command. Runs in executor thread."""
        clim = self._vehicle.climatization
        cmd_obj = clim.commands.commands.get(_CLIMATIZATION_COMMAND_KEY)
        if cmd_obj is None:
            vin = self._vehicle.vin.value
            raise HomeAssistantError(
                f"Climatization command not available for vehicle {vin}"
            )
        cmd_obj.value = {"command": command}

    def _set_target_temperature(self, temp: float, unit: Temperature) -> None:
        """Set the climatization target temperature. Runs in executor thread.

        Assigning the changeable settings attribute triggers the connector's
        set hook, which PUTs the new settings to the VW API. The start-stop
        command payload does NOT support a temperature — this is the only path
        the connector honours.
        """
        attr = self._target_temperature_attr
        if attr is None or not attr.enabled:
            vin = self._vehicle.vin.value
            raise HomeAssistantError(
                f"Climatization target temperature not available for vehicle {vin}"
            )
        try:
            attr.set_value(temp, unit=unit)
        except Exception as err:
            raise HomeAssistantError(
                f"Could not set climatization target temperature: {err}"
            ) from err

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode (start or stop climatization)."""
        command = "stop" if hvac_mode == HVACMode.OFF else "start"
        await self.hass.async_add_executor_job(
            self._send_climatization_command, command
        )
        await self.coordinator.async_refresh_after_command()

    async def async_turn_on(self) -> None:
        """Start climatization."""
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_turn_off(self) -> None:
        """Stop climatization."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new climatization target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        await self.hass.async_add_executor_job(
            self._set_target_temperature, temp, self._display_unit
        )
        await self.coordinator.async_refresh_after_command()
