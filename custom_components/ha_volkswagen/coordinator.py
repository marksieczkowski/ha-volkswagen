"""DataUpdateCoordinator for the HA Volkswagen integration."""
from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import TYPE_CHECKING

from carconnectivity import carconnectivity as cc

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_COUNTRY,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SELECTED_VINS,
    CONF_SPIN,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    TOKENSTORE_FILENAME_TEMPLATE,
)

if TYPE_CHECKING:
    from carconnectivity.garage import Garage

    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


def build_carconnectivity_config(data: dict) -> dict:
    """Build the config dict expected by CarConnectivity from config entry data."""
    connector_config: dict = {
        "username": data[CONF_USERNAME],
        "password": data[CONF_PASSWORD],
        "interval": data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    }
    if data.get(CONF_COUNTRY):
        connector_config["country"] = data[CONF_COUNTRY]
    if data.get(CONF_SPIN):
        connector_config["spin"] = data[CONF_SPIN]

    return {
        "carConnectivity": {
            "connectors": [
                {
                    "type": "volkswagen_na",
                    "config": connector_config,
                }
            ]
        }
    }


def get_tokenstore_path(config_dir: str, entry_id: str) -> str:
    """Return the path for the tokenstore file for a given config entry."""
    storage_dir = os.path.join(config_dir, ".storage")
    os.makedirs(storage_dir, exist_ok=True)
    filename = TOKENSTORE_FILENAME_TEMPLATE.format(entry_id=entry_id)
    return os.path.join(storage_dir, filename)


class VolkswagenDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator that owns a CarConnectivity instance and drives polling."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialise the coordinator."""
        self.car_connectivity: cc.CarConnectivity | None = None

        scan_interval = config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        # Pass config_entry to the parent so self.config_entry is set correctly
        # (DataUpdateCoordinator sets self.config_entry = config_entry internally)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            config_entry=config_entry,
        )

    async def async_setup(self) -> None:
        """Create and start the CarConnectivity instance.

        Must be awaited once before async_config_entry_first_refresh().
        Runs blocking I/O in the executor.
        """
        config_dict = build_carconnectivity_config(self.config_entry.data)
        tokenstore_path = get_tokenstore_path(
            self.hass.config.config_dir, self.config_entry.entry_id
        )

        def _startup_sync() -> cc.CarConnectivity:
            instance = cc.CarConnectivity(
                config=config_dict,
                tokenstore_file=tokenstore_path,
            )
            instance.startup()
            return instance

        self.car_connectivity = await self.hass.async_add_executor_job(_startup_sync)

    def _fetch_all_sync(self) -> Garage:
        """Blocking fetch — runs in the executor thread."""
        assert self.car_connectivity is not None
        self.car_connectivity.fetch_all()
        self.car_connectivity.persist()
        garage = self.car_connectivity.get_garage()
        if garage is None:
            raise UpdateFailed("CarConnectivity returned no garage")
        return garage

    async def _async_update_data(self) -> Garage:
        """Fetch latest data from the VW API."""
        if self.car_connectivity is None:
            raise UpdateFailed("CarConnectivity not initialised")
        try:
            return await self.hass.async_add_executor_job(self._fetch_all_sync)
        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            # Surface authentication errors distinctly so HA can prompt re-auth
            err_str = str(err).lower()
            if any(word in err_str for word in ("auth", "unauthorized", "401", "403", "token")):
                raise ConfigEntryAuthFailed(
                    f"Authentication failed for Volkswagen account: {err}"
                ) from err
            raise UpdateFailed(f"Error communicating with Volkswagen API: {err}") from err

    def get_vehicles(self) -> list:
        """Return vehicles, optionally filtered to the user's selected VINs."""
        if self.data is None:
            return []
        all_vehicles = list(self.data.list_vehicles())
        selected = self.config_entry.data.get(CONF_SELECTED_VINS, [])
        if not selected:
            return all_vehicles
        return [v for v in all_vehicles if v.vin.value in selected]

    async def async_shutdown(self) -> None:
        """Shut down the CarConnectivity instance (saves tokens/cache)."""
        if self.car_connectivity is not None:
            await self.hass.async_add_executor_job(self.car_connectivity.shutdown)
            self.car_connectivity = None
