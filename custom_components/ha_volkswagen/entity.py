"""Base entity for the HA Volkswagen integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from carconnectivity.vehicle import GenericVehicle

    from .coordinator import VolkswagenDataUpdateCoordinator


class VolkswagenBaseEntity(CoordinatorEntity["VolkswagenDataUpdateCoordinator"]):
    """Base class for all Volkswagen entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VolkswagenDataUpdateCoordinator,
        vehicle: GenericVehicle,
    ) -> None:
        """Initialise the base entity."""
        super().__init__(coordinator)
        self._vehicle = vehicle

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this vehicle."""
        vin = self._vehicle.vin.value or "unknown"

        model: str | None = None
        if self._vehicle.model.enabled:
            model = self._vehicle.model.value

        year: str | None = None
        if self._vehicle.model_year.enabled:
            year = str(self._vehicle.model_year.value)

        model_with_year = (
            f"{year} {model}" if year and model else (model or "Volkswagen")
        )

        return DeviceInfo(
            identifiers={(DOMAIN, vin)},
            name=model_with_year,
            manufacturer="Volkswagen",
            model=model,
            serial_number=vin,
        )

    @property
    def available(self) -> bool:
        """Return True when the vehicle is reachable."""
        if not super().available:
            return False
        conn = self._vehicle.connection_state
        # If the API doesn't provide a connection_state (conn.enabled is False),
        # treat the vehicle as available — the VW NA API omits this field.
        if not conn.enabled:
            return True
        # When a connection state IS provided, only mark available if online/reachable.
        return conn.value.value.lower() in {"online", "reachable"}
