"""Tests for the Volkswagen config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_volkswagen.const import (
    CONF_COUNTRY,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SELECTED_VINS,
    CONF_SPIN,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

from .conftest import (
    TEST_COUNTRY,
    TEST_PASSWORD,
    TEST_USERNAME,
    TEST_VIN,
    make_mock_electric_vehicle,
)


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Prevent HA from auto-loading the integration after entry creation."""
    with patch(
        "custom_components.ha_volkswagen.async_setup_entry",
        return_value=True,
    ):
        yield


_STEP_USER_INPUT: dict[str, Any] = {
    CONF_USERNAME: TEST_USERNAME,
    CONF_PASSWORD: TEST_PASSWORD,
    CONF_COUNTRY: TEST_COUNTRY,
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}

_STEP_SELECT_INPUT: dict[str, Any] = {
    CONF_SELECTED_VINS: [TEST_VIN],
}


def _patch_connect(vehicles: list | None = None, raises: Exception | None = None):
    """Patch _try_connect in the config flow module."""
    if raises is not None:
        return patch(
            "custom_components.ha_volkswagen.config_flow._try_connect",
            side_effect=raises,
        )
    veh_list = vehicles if vehicles is not None else [make_mock_electric_vehicle()]
    return patch(
        "custom_components.ha_volkswagen.config_flow._try_connect",
        return_value=veh_list,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_flow_creates_entry(hass):
    """A complete config flow should create a config entry."""
    with _patch_connect():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=_STEP_USER_INPUT
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "select_vehicle"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=_STEP_SELECT_INPUT
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == TEST_USERNAME
    assert result["data"][CONF_COUNTRY] == TEST_COUNTRY
    assert result["data"][CONF_SELECTED_VINS] == [TEST_VIN]


@pytest.mark.asyncio
async def test_no_vehicles_creates_entry_immediately(hass):
    """When no vehicles are discovered the flow should skip vehicle selection."""
    with _patch_connect(vehicles=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=_STEP_USER_INPUT
        )

    # Skips straight to CREATE_ENTRY when garage is empty
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SELECTED_VINS] == []


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_auth_shows_error(hass):
    """Authentication failures should show invalid_auth error on the form."""
    with _patch_connect(raises=Exception("401 Unauthorized")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=_STEP_USER_INPUT
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_cannot_connect_shows_error(hass):
    """Connection failures should show cannot_connect error on the form."""
    with _patch_connect(raises=ConnectionError("timeout")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=_STEP_USER_INPUT
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_duplicate_entry_aborts(hass):
    """A second config entry for the same account should be aborted."""
    with _patch_connect():
        # First entry — succeeds
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=_STEP_USER_INPUT
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=_STEP_SELECT_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY

        # Second entry — same credentials
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], user_input=_STEP_USER_INPUT
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Reauth flow
# ---------------------------------------------------------------------------


def _make_configured_entry(hass) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**_STEP_USER_INPUT, CONF_SELECTED_VINS: [TEST_VIN]},
        unique_id=f"{TEST_USERNAME}_{TEST_COUNTRY}",
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.asyncio
async def test_reauth_flow_updates_password(hass):
    """A successful reauth should update the stored password and reload."""
    entry = _make_configured_entry(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with _patch_connect():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "new-password"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-password"
    # Username and selections must be preserved
    assert entry.data[CONF_USERNAME] == TEST_USERNAME
    assert entry.data[CONF_SELECTED_VINS] == [TEST_VIN]


@pytest.mark.asyncio
async def test_reauth_flow_invalid_password_shows_error(hass):
    """A rejected password should re-show the form with invalid_auth."""
    entry = _make_configured_entry(hass)

    result = await entry.start_reauth_flow(hass)

    with _patch_connect(raises=Exception("401 Unauthorized")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "wrong-password"}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == "invalid_auth"
    # The stored password must be untouched
    assert entry.data[CONF_PASSWORD] == TEST_PASSWORD


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_options_flow_updates_scan_interval(hass):
    """Options flow should update the scan interval."""
    with _patch_connect():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=_STEP_USER_INPUT
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=_STEP_SELECT_INPUT
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    entry = result["result"]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_SCAN_INTERVAL: 600}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SCAN_INTERVAL] == 600


@pytest.mark.asyncio
async def test_options_flow_sets_spin(hass):
    """The S-PIN can be added after initial setup via the options flow."""
    with _patch_connect():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=_STEP_USER_INPUT
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=_STEP_SELECT_INPUT
        )

    entry = result["result"]
    # Initial setup did not include an S-PIN
    assert not entry.data.get(CONF_SPIN)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL, CONF_SPIN: "1234"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SPIN] == "1234"
    assert entry.options[CONF_SPIN] == "1234"
