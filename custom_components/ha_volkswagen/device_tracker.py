"""Device tracker platform for the HA Volkswagen integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.device_tracker.entity import TrackerEntity
from homeassistant.core import callback

from .entity import VolkswagenBaseEntity

if TYPE_CHECKING:
    from carconnectivity.vehicle import GenericVehicle
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import VolkswagenConfigEntry, VolkswagenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VolkswagenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Volkswagen device tracker entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        VolkswagenDeviceTracker(coordinator, vehicle)
        for vehicle in coordinator.get_vehicles()
    )


class VolkswagenDeviceTracker(VolkswagenBaseEntity, TrackerEntity):
    """Device tracker for a Volkswagen vehicle's GPS position."""

    _attr_icon = "mdi:car"
    # Override TrackerEntity's default entity_category of DIAGNOSTIC so the entity
    # appears in the main device controls rather than the diagnostics section.
    _attr_entity_category = None

    def __init__(
        self,
        coordinator: VolkswagenDataUpdateCoordinator,
        vehicle: GenericVehicle,
    ) -> None:
        """Initialise the device tracker."""
        super().__init__(coordinator, vehicle)
        self._attr_unique_id = f"{vehicle.vin.value}_position"
        self._attr_name = "Location"
        self._update_position()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh the tracked position when the coordinator updates."""
        self._update_position()
        super()._handle_coordinator_update()

    def _update_position(self) -> None:
        """Copy the vehicle's GPS position into the tracker attributes."""
        pos = self._vehicle.position
        self._attr_latitude = (
            pos.latitude.value if pos is not None and pos.latitude.enabled else None
        )
        self._attr_longitude = (
            pos.longitude.value if pos is not None and pos.longitude.enabled else None
        )

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
