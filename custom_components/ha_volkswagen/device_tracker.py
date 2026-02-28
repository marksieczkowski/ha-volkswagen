"""Device tracker platform for the HA Volkswagen integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from carconnectivity.position import Position

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity

from .const import DOMAIN
from .entity import VolkswagenBaseEntity

if TYPE_CHECKING:
    from carconnectivity.vehicle import GenericVehicle

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import VolkswagenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Volkswagen device tracker entities."""
    coordinator: VolkswagenDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        VolkswagenDeviceTracker(coordinator, vehicle)
        for vehicle in coordinator.get_vehicles()
    )


class VolkswagenDeviceTracker(VolkswagenBaseEntity, TrackerEntity):
    """Device tracker for a Volkswagen vehicle's GPS position."""

    _attr_source_type = SourceType.GPS
    _attr_icon = "mdi:car"

    def __init__(
        self,
        coordinator: VolkswagenDataUpdateCoordinator,
        vehicle: GenericVehicle,
    ) -> None:
        """Initialise the device tracker."""
        super().__init__(coordinator, vehicle)
        self._attr_unique_id = f"{vehicle.vin.value}_position"
        self._attr_name = "Location"

    @property
    def latitude(self) -> float | None:
        """Return the latitude of the vehicle."""
        pos = self._vehicle.position
        if pos is None:
            return None
        if pos.latitude.enabled:
            return pos.latitude.value
        return None

    @property
    def longitude(self) -> float | None:
        """Return the longitude of the vehicle."""
        pos = self._vehicle.position
        if pos is None:
            return None
        if pos.longitude.enabled:
            return pos.longitude.value
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {}
        pos = self._vehicle.position
        if pos is None:
            return attrs

        if pos.position_type.enabled:
            attrs["position_type"] = pos.position_type.value.value

        if pos.altitude.enabled:
            attrs["altitude_m"] = pos.altitude.value

        if pos.heading.enabled:
            attrs["heading_deg"] = pos.heading.value

        return attrs
