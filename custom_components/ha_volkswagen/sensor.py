"""Sensor platform for the HA Volkswagen integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from carconnectivity_connectors.volkswagen_na.vehicle import (
    VolkswagenNACombustionVehicle,
    VolkswagenNAElectricVehicle,
    VolkswagenNAHybridVehicle,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfLength,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTemperature,
)

from .const import DOMAIN
from .entity import VolkswagenBaseEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from carconnectivity.vehicle import GenericVehicle
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import VolkswagenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _safe_attr(vehicle: GenericVehicle, *attr_path: str) -> Any:
    """Safely traverse attribute names, returning None if any are disabled/absent."""
    obj = vehicle
    for attr in attr_path:
        obj = getattr(obj, attr, None)
        if obj is None:
            return None
    return obj


@dataclass(frozen=True, kw_only=True)
class VolkswagenSensorDescription(SensorEntityDescription):
    """Describe a Volkswagen sensor."""

    value_fn: Callable[[GenericVehicle], Any] = lambda _: None
    supported_fn: Callable[[GenericVehicle], bool] = lambda _: True


SENSOR_DESCRIPTIONS: tuple[VolkswagenSensorDescription, ...] = (
    # NOTE: The VW NA connector sets vehicle.odometer from currentMileage, but a later
    # code path in the same function unconditionally resets it to None when the API
    # response lacks a 'measurements' key (which the NA API omits for EV models).
    # This is a bug in carconnectivity-connector-volkswagen-na; disable the entity by
    # default so it doesn't show a confusing "unknown" value until upstream fixes it.
    VolkswagenSensorDescription(
        key="odometer",
        translation_key="odometer",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        entity_registry_enabled_default=False,
        value_fn=lambda v: v.odometer.value if v.odometer.enabled else None,
    ),
    VolkswagenSensorDescription(
        key="battery_soc",
        translation_key="battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda v: (
            v.get_electric_drive().level.value
            if v.get_electric_drive() and v.get_electric_drive().level.enabled
            else None
        ),
        supported_fn=lambda v: isinstance(
            v, (VolkswagenNAElectricVehicle, VolkswagenNAHybridVehicle)
        ),
    ),
    VolkswagenSensorDescription(
        key="ev_range",
        translation_key="ev_range",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda v: (
            v.get_electric_drive().range.value
            if v.get_electric_drive() and v.get_electric_drive().range.enabled
            else None
        ),
        supported_fn=lambda v: isinstance(
            v, (VolkswagenNAElectricVehicle, VolkswagenNAHybridVehicle)
        ),
    ),
    VolkswagenSensorDescription(
        key="fuel_level",
        translation_key="fuel_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:gas-station",
        value_fn=lambda v: (
            v.get_combustion_drive().level.value
            if v.get_combustion_drive() and v.get_combustion_drive().level.enabled
            else None
        ),
        supported_fn=lambda v: isinstance(
            v, (VolkswagenNACombustionVehicle, VolkswagenNAHybridVehicle)
        ),
    ),
    VolkswagenSensorDescription(
        key="fuel_range",
        translation_key="fuel_range",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        icon="mdi:gas-station",
        value_fn=lambda v: (
            v.get_combustion_drive().range.value
            if v.get_combustion_drive() and v.get_combustion_drive().range.enabled
            else None
        ),
        supported_fn=lambda v: isinstance(
            v, (VolkswagenNACombustionVehicle, VolkswagenNAHybridVehicle)
        ),
    ),
    # NOTE: Populated from data['measurements']['temperatureOutsideStatus'], which the
    # VW NA API omits for EV models. Disabled by default to avoid showing "unknown".
    VolkswagenSensorDescription(
        key="outside_temperature",
        translation_key="outside_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
        value_fn=lambda v: v.outside_temperature.value
        if v.outside_temperature.enabled
        else None,
    ),
    VolkswagenSensorDescription(
        key="charge_power",
        translation_key="charge_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        value_fn=lambda v: v.charging.power.value if v.charging.power.enabled else None,
        supported_fn=lambda v: isinstance(
            v, (VolkswagenNAElectricVehicle, VolkswagenNAHybridVehicle)
        ),
    ),
    VolkswagenSensorDescription(
        key="charge_rate",
        translation_key="charge_rate",
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda v: v.charging.rate.value if v.charging.rate.enabled else None,
        supported_fn=lambda v: isinstance(
            v, (VolkswagenNAElectricVehicle, VolkswagenNAHybridVehicle)
        ),
    ),
    VolkswagenSensorDescription(
        key="charging_state",
        translation_key="charging_state",
        icon="mdi:ev-station",
        value_fn=lambda v: (
            getattr(v.charging.state.value, "value", str(v.charging.state.value))
            if v.charging.state.enabled
            else None
        ),
        supported_fn=lambda v: isinstance(
            v, (VolkswagenNAElectricVehicle, VolkswagenNAHybridVehicle)
        ),
    ),
    VolkswagenSensorDescription(
        key="inspection_due_at",
        translation_key="inspection_due_at",
        device_class=SensorDeviceClass.DATE,
        entity_registry_enabled_default=False,
        value_fn=lambda v: (
            v.maintenance.inspection_due_at.value
            if v.maintenance.inspection_due_at.enabled
            else None
        ),
    ),
    VolkswagenSensorDescription(
        key="inspection_due_after",
        translation_key="inspection_due_after",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        entity_registry_enabled_default=False,
        value_fn=lambda v: (
            v.maintenance.inspection_due_after.value
            if v.maintenance.inspection_due_after.enabled
            else None
        ),
    ),
    VolkswagenSensorDescription(
        key="oil_service_due_at",
        translation_key="oil_service_due_at",
        device_class=SensorDeviceClass.DATE,
        entity_registry_enabled_default=False,
        value_fn=lambda v: (
            v.maintenance.oil_service_due_at.value
            if v.maintenance.oil_service_due_at.enabled
            else None
        ),
        supported_fn=lambda v: isinstance(
            v, (VolkswagenNACombustionVehicle, VolkswagenNAHybridVehicle)
        ),
    ),
    VolkswagenSensorDescription(
        key="oil_service_due_after",
        translation_key="oil_service_due_after",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        entity_registry_enabled_default=False,
        value_fn=lambda v: (
            v.maintenance.oil_service_due_after.value
            if v.maintenance.oil_service_due_after.enabled
            else None
        ),
        supported_fn=lambda v: isinstance(
            v, (VolkswagenNACombustionVehicle, VolkswagenNAHybridVehicle)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Volkswagen sensor entities."""
    coordinator: VolkswagenDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[VolkswagenSensor] = []
    for vehicle in coordinator.get_vehicles():
        for description in SENSOR_DESCRIPTIONS:
            try:
                if description.supported_fn(vehicle):
                    entities.append(VolkswagenSensor(coordinator, vehicle, description))
            except Exception:
                _LOGGER.debug(
                    "Skipping sensor %s for %s", description.key, vehicle.vin.value
                )

    async_add_entities(entities)


class VolkswagenSensor(VolkswagenBaseEntity, SensorEntity):
    """A sensor entity for a Volkswagen vehicle attribute."""

    entity_description: VolkswagenSensorDescription

    def __init__(
        self,
        coordinator: VolkswagenDataUpdateCoordinator,
        vehicle: GenericVehicle,
        description: VolkswagenSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{vehicle.vin.value}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the current value of this sensor."""
        try:
            return self.entity_description.value_fn(self._vehicle)
        except Exception:
            return None
