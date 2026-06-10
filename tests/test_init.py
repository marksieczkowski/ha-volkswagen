"""Tests for integration setup and unload."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_volkswagen.const import DOMAIN
from custom_components.ha_volkswagen.coordinator import VolkswagenDataUpdateCoordinator

from .conftest import CONFIG_ENTRY_DATA


async def test_setup_and_unload_entry(hass, mock_carconnectivity):
    """Full setup should store the coordinator in runtime_data; unload cleans up."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_ENTRY_DATA, entry_id="test_entry_id"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    coordinator = entry.runtime_data
    assert isinstance(coordinator, VolkswagenDataUpdateCoordinator)
    mock_carconnectivity.fetch_all.assert_called()
    mock_carconnectivity.startup.assert_not_called()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    # Tokens persisted and instance released on unload
    mock_carconnectivity.persist.assert_called()
    assert coordinator.car_connectivity is None


async def test_setup_entry_not_ready_on_connect_failure(hass, mock_garage):
    """A failing CarConnectivity constructor should put the entry in retry state."""
    from unittest.mock import patch

    entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_ENTRY_DATA, entry_id="test_entry_id"
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.ha_volkswagen.coordinator.cc.CarConnectivity",
        side_effect=ConnectionError("no network"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
