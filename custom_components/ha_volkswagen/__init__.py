"""Home Assistant integration for Volkswagen North America vehicles."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .coordinator import VolkswagenDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import VolkswagenConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.CLIMATE,
    Platform.SWITCH,
]


async def _async_update_entry(
    hass: HomeAssistant, entry: VolkswagenConfigEntry
) -> None:
    """Handle options updates — clear cached sensor units then reload."""
    registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if "sensor.private" in entity_entry.options:
            registry.async_update_entity_options(
                entity_entry.entity_id, "sensor.private", None
            )
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: VolkswagenConfigEntry) -> bool:
    """Set up Volkswagen integration from a config entry."""
    coordinator = VolkswagenDataUpdateCoordinator(hass, entry)

    try:
        await coordinator.async_setup()
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Could not connect to Volkswagen API: {err}"
        ) from err

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VolkswagenConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_shutdown()
    return unload_ok
