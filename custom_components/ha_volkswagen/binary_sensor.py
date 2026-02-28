"""Binary sensor platform for the HA Volkswagen integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from carconnectivity.doors import Doors
from carconnectivity.lights import Lights
from carconnectivity.windows import Windows
from carconnectivity_connectors.volkswagen_na.vehicle import (
    VolkswagenNAElectricVehicle,
    VolkswagenNAHybridVehicle,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .const import DOMAIN
from .entity import VolkswagenBaseEntity

if TYPE_CHECKING:
    from carconnectivity.vehicle import GenericVehicle

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import VolkswagenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class VolkswagenBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a Volkswagen binary sensor."""

    value_fn: Callable[[GenericVehicle], bool | None] = lambda _: None
    supported_fn: Callable[[GenericVehicle], bool] = lambda _: True


def _door_open(vehicle: GenericVehicle, door_key: str) -> bool | None:
    """Return True if a specific door is open."""
    doors_dict = vehicle.doors.doors
    door = doors_dict.get(door_key)
    if door is None or not door.open_state.enabled:
        return None
    return door.open_state.value == Doors.OpenState.OPEN


BINARY_SENSOR_DESCRIPTIONS: tuple[VolkswagenBinarySensorDescription, ...] = (
    # Overall door lock — True means UNLOCKED (HA LOCK device class convention)
    VolkswagenBinarySensorDescription(
        key="doors_locked",
        translation_key="doors_locked",
        device_class=BinarySensorDeviceClass.LOCK,
        value_fn=lambda v: (
            v.doors.lock_state.value == Doors.LockState.UNLOCKED
            if v.doors.lock_state.enabled
            else None
        ),
    ),
    # Individual door open states
    VolkswagenBinarySensorDescription(
        key="door_front_left",
        translation_key="door_front_left",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_registry_enabled_default=False,
        value_fn=lambda v: _door_open(v, "frontLeft"),
    ),
    VolkswagenBinarySensorDescription(
        key="door_front_right",
        translation_key="door_front_right",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_registry_enabled_default=False,
        value_fn=lambda v: _door_open(v, "frontRight"),
    ),
    VolkswagenBinarySensorDescription(
        key="door_rear_left",
        translation_key="door_rear_left",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_registry_enabled_default=False,
        value_fn=lambda v: _door_open(v, "rearLeft"),
    ),
    VolkswagenBinarySensorDescription(
        key="door_rear_right",
        translation_key="door_rear_right",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_registry_enabled_default=False,
        value_fn=lambda v: _door_open(v, "rearRight"),
    ),
    VolkswagenBinarySensorDescription(
        key="trunk",
        translation_key="trunk",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_registry_enabled_default=False,
        value_fn=lambda v: _door_open(v, "trunk"),
    ),
    # Windows — overall open state
    VolkswagenBinarySensorDescription(
        key="windows_open",
        translation_key="windows_open",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda v: (
            v.windows.open_state.value == Windows.OpenState.OPEN
            if v.windows.open_state.enabled
            else None
        ),
    ),
    # Exterior lights
    VolkswagenBinarySensorDescription(
        key="lights_on",
        translation_key="lights_on",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda v: (
            v.lights.light_state.value == Lights.LightState.ON
            if v.lights.light_state.enabled
            else None
        ),
    ),
    # EV / Hybrid — charging cable connected
    VolkswagenBinarySensorDescription(
        key="charging_connected",
        translation_key="charging_connected",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda v: (
            v.charging.connector.connection_state.enabled
            and v.charging.connector.connection_state.value is not None
            and v.charging.connector.connection_state.value.value.lower() == "connected"
            if v.charging.connector.connection_state.enabled
            else None
        ),
        supported_fn=lambda v: isinstance(v, (VolkswagenNAElectricVehicle, VolkswagenNAHybridVehicle)),
    ),
    # EV / Hybrid — actively charging
    VolkswagenBinarySensorDescription(
        key="charging_active",
        translation_key="charging_active",
        icon="mdi:ev-station",
        value_fn=lambda v: (
            v.charging.state.value.value.lower() == "charginghvbattery"
            if v.charging.state.enabled
            else None
        ),
        supported_fn=lambda v: isinstance(v, (VolkswagenNAElectricVehicle, VolkswagenNAHybridVehicle)),
    ),
    # Vehicle network connectivity
    VolkswagenBinarySensorDescription(
        key="vehicle_online",
        translation_key="vehicle_online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda v: (
            v.connection_state.value.value.lower() in {"online", "reachable"}
            if v.connection_state.enabled
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Volkswagen binary sensor entities."""
    coordinator: VolkswagenDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[VolkswagenBinarySensor] = []
    for vehicle in coordinator.get_vehicles():
        for description in BINARY_SENSOR_DESCRIPTIONS:
            try:
                if description.supported_fn(vehicle):
                    entities.append(
                        VolkswagenBinarySensor(coordinator, vehicle, description)
                    )
            except Exception:
                _LOGGER.debug(
                    "Skipping binary sensor %s for %s", description.key, vehicle.vin.value
                )

    async_add_entities(entities)


class VolkswagenBinarySensor(VolkswagenBaseEntity, BinarySensorEntity):
    """A binary sensor entity for a Volkswagen vehicle attribute."""

    entity_description: VolkswagenBinarySensorDescription

    def __init__(
        self,
        coordinator: VolkswagenDataUpdateCoordinator,
        vehicle: GenericVehicle,
        description: VolkswagenBinarySensorDescription,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{vehicle.vin.value}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the current state of this binary sensor."""
        try:
            return self.entity_description.value_fn(self._vehicle)
        except Exception:
            return None
