"""Tests for the VolkswagenDataUpdateCoordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_volkswagen.const import (
    CONF_SELECTED_VINS,
    DOMAIN,
)
from custom_components.ha_volkswagen.coordinator import VolkswagenDataUpdateCoordinator

from .conftest import (
    CONFIG_ENTRY_DATA,
    TEST_VIN,
    make_mock_electric_vehicle,
    make_mock_garage,
)


def _make_entry(**overrides) -> MockConfigEntry:
    data = {**CONFIG_ENTRY_DATA, **overrides}
    return MockConfigEntry(domain=DOMAIN, data=data, entry_id="test_entry_id")


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return _make_entry()


# ---------------------------------------------------------------------------
# scan interval — options must take precedence over original setup data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_interval_from_options_overrides_data(hass):
    """An interval changed via the options flow must be applied."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_ENTRY_DATA, "scan_interval": 300},
        options={"scan_interval": 600},
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)
    coordinator = VolkswagenDataUpdateCoordinator(hass, entry)

    assert coordinator.update_interval is not None
    assert coordinator.update_interval.total_seconds() == 600


@pytest.mark.asyncio
async def test_options_scan_interval_passed_to_connector_config(
    hass, mock_carconnectivity
):
    """build_carconnectivity_config must see the options-flow interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_ENTRY_DATA, "scan_interval": 300},
        options={"scan_interval": 600},
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)
    coordinator = VolkswagenDataUpdateCoordinator(hass, entry)

    with patch(
        "custom_components.ha_volkswagen.coordinator.build_carconnectivity_config"
    ) as mock_build:
        await coordinator.async_setup()

    merged = mock_build.call_args[0][0]
    assert merged["scan_interval"] == 600


# ---------------------------------------------------------------------------
# async_setup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_setup_creates_car_connectivity(
    hass, mock_carconnectivity, config_entry
):
    """async_setup should create and start a CarConnectivity instance."""
    config_entry.add_to_hass(hass)
    coordinator = VolkswagenDataUpdateCoordinator(hass, config_entry)

    await coordinator.async_setup()

    assert coordinator.car_connectivity is mock_carconnectivity
    mock_carconnectivity.startup.assert_not_called()


# ---------------------------------------------------------------------------
# _async_update_data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_refresh_returns_garage(
    hass, mock_carconnectivity, config_entry, mock_garage
):
    """After a refresh the coordinator data should be the garage."""
    config_entry.add_to_hass(hass)
    coordinator = VolkswagenDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_setup()

    mock_carconnectivity.get_garage.return_value = mock_garage

    await coordinator.async_refresh()

    assert coordinator.data is mock_garage
    mock_carconnectivity.fetch_all.assert_called_once()
    mock_carconnectivity.persist.assert_called_once()


@pytest.mark.asyncio
async def test_update_failure_raises_update_failed(
    hass, mock_carconnectivity, config_entry
):
    """When fetch_all raises a non-auth error UpdateFailed should be raised."""
    config_entry.add_to_hass(hass)
    coordinator = VolkswagenDataUpdateCoordinator(hass, config_entry)
    coordinator.car_connectivity = mock_carconnectivity

    mock_carconnectivity.fetch_all.side_effect = ConnectionError("timeout")
    mock_carconnectivity.get_garage.return_value = MagicMock()

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_none_garage_raises_update_failed(
    hass, mock_carconnectivity, config_entry
):
    """When get_garage returns None UpdateFailed should be raised."""
    config_entry.add_to_hass(hass)
    coordinator = VolkswagenDataUpdateCoordinator(hass, config_entry)
    coordinator.car_connectivity = mock_carconnectivity

    mock_carconnectivity.fetch_all.return_value = None
    mock_carconnectivity.get_garage.return_value = None

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


# ---------------------------------------------------------------------------
# get_vehicles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_vehicles_returns_all_when_no_filter(
    hass, mock_carconnectivity, config_entry, mock_garage, mock_electric_vehicle
):
    """get_vehicles should return all vehicles when CONF_SELECTED_VINS is empty."""
    config_entry.add_to_hass(hass)
    coordinator = VolkswagenDataUpdateCoordinator(hass, config_entry)
    coordinator.car_connectivity = mock_carconnectivity
    coordinator.data = mock_garage

    vehicles = coordinator.get_vehicles()

    assert len(vehicles) == 1
    assert vehicles[0] is mock_electric_vehicle


@pytest.mark.asyncio
async def test_get_vehicles_filters_by_vin(hass, mock_carconnectivity, mock_garage):
    """get_vehicles should filter by CONF_SELECTED_VINS when set."""
    other_vin = "OTHER_VIN_0000"
    vehicle1 = make_mock_electric_vehicle(vin=TEST_VIN)
    vehicle2 = make_mock_electric_vehicle(vin=other_vin)
    garage = make_mock_garage([vehicle1, vehicle2])

    entry = _make_entry(**{CONF_SELECTED_VINS: [TEST_VIN]})
    entry.add_to_hass(hass)
    coordinator = VolkswagenDataUpdateCoordinator(hass, entry)
    coordinator.car_connectivity = mock_carconnectivity
    coordinator.data = garage

    vehicles = coordinator.get_vehicles()

    assert len(vehicles) == 1
    assert vehicles[0].vin.value == TEST_VIN


@pytest.mark.asyncio
async def test_get_vehicles_returns_empty_when_no_data(hass, config_entry):
    """get_vehicles should return [] when coordinator.data is None."""
    config_entry.add_to_hass(hass)
    coordinator = VolkswagenDataUpdateCoordinator(hass, config_entry)
    coordinator.data = None

    assert coordinator.get_vehicles() == []


# ---------------------------------------------------------------------------
# async_refresh_after_command
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_refresh_after_command_schedules_tasks(
    hass, mock_carconnectivity, config_entry
):
    """Should schedule 3 tracked background refresh tasks on the config entry."""
    config_entry.add_to_hass(hass)
    coordinator = VolkswagenDataUpdateCoordinator(hass, config_entry)
    coordinator.car_connectivity = mock_carconnectivity
    coordinator.data = MagicMock()

    scheduled = []

    def _fake_background_task(hass_arg, coro, name=None, **kwargs):
        scheduled.append(name)
        coro.close()

    with patch.object(
        config_entry,
        "async_create_background_task",
        side_effect=_fake_background_task,
    ):
        await coordinator.async_refresh_after_command()

    assert len(scheduled) == 3


@pytest.mark.asyncio
async def test_delayed_refresh_requests_refresh(hass, config_entry):
    """The delayed task should sleep then request a coordinator refresh."""
    config_entry.add_to_hass(hass)
    coordinator = VolkswagenDataUpdateCoordinator(hass, config_entry)

    with (
        patch.object(
            coordinator, "async_request_refresh", new_callable=AsyncMock
        ) as mock_refresh,
        patch(
            "custom_components.ha_volkswagen.coordinator.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
    ):
        await coordinator._delayed_refresh(20)

    mock_sleep.assert_awaited_once_with(20)
    mock_refresh.assert_awaited_once()


# ---------------------------------------------------------------------------
# async_shutdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shutdown_calls_car_connectivity_shutdown(
    hass, mock_carconnectivity, config_entry
):
    """async_shutdown should call CarConnectivity.shutdown()."""
    config_entry.add_to_hass(hass)
    coordinator = VolkswagenDataUpdateCoordinator(hass, config_entry)
    coordinator.car_connectivity = mock_carconnectivity

    await coordinator.async_shutdown()

    mock_carconnectivity.persist.assert_called_once()
    mock_carconnectivity.shutdown.assert_not_called()
    assert coordinator.car_connectivity is None
