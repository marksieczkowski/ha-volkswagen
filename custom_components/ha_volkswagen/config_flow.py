"""Config flow for the HA Volkswagen integration."""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

import voluptuous as vol
from carconnectivity import carconnectivity as cc

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_COUNTRY,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SELECTED_VINS,
    CONF_SPIN,
    CONF_USERNAME,
    DEFAULT_COUNTRY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    SUPPORTED_COUNTRIES,
)
from .coordinator import build_carconnectivity_config, get_tokenstore_path

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_COUNTRY, default=DEFAULT_COUNTRY): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value="us", label="United States"),
                    SelectOptionDict(value="ca", label="Canada (experimental)"),
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)
        ),
        vol.Optional(CONF_SPIN): str,
    }
)


def _try_connect(config_dict: dict, tokenstore_path: str | None = None) -> list:
    """Attempt to connect and return discovered vehicles.  Runs in executor thread."""
    if tokenstore_path is not None:
        # Reuse an existing tokenstore so we don't force a fresh VW OAuth flow
        # every validation attempt (VW rate-limits rapid re-auths).
        instance = cc.CarConnectivity(
            config=config_dict, tokenstore_file=tokenstore_path
        )
        try:
            instance.fetch_all()
            instance.persist()
            garage = instance.get_garage()
            if garage is None:
                return []
            return list(garage.list_vehicles())
        except Exception:
            instance.persist()
            raise
    else:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_tokenstore = os.path.join(tmp_dir, "tokenstore")
            instance = cc.CarConnectivity(
                config=config_dict, tokenstore_file=tmp_tokenstore
            )
            try:
                instance.fetch_all()
                garage = instance.get_garage()
                if garage is None:
                    return []
                return list(garage.list_vehicles())
            finally:
                instance.persist()


class VolkswagenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Volkswagen (North America)."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise flow state."""
        self._user_input: dict[str, Any] = {}
        self._discovered_vehicles: list = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: collect credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            country = user_input.get(CONF_COUNTRY, DEFAULT_COUNTRY)

            # Prevent duplicate config entries for the same account
            await self.async_set_unique_id(f"{username}_{country}")
            self._abort_if_unique_id_configured()

            config_dict = build_carconnectivity_config(user_input)
            # Re-use tokenstore if it already exists for this account — avoids
            # re-authenticating against VW's server on every validation attempt.
            tokenstore_path = get_tokenstore_path(
                self.hass.config.config_dir,
                f"{username}_{country}",
            )
            try:
                vehicles = await self.hass.async_add_executor_job(
                    _try_connect, config_dict, tokenstore_path
                )
            except Exception as err:
                err_str = str(err).lower()
                _LOGGER.debug("Connection attempt failed: %s", err)
                # INVALID_REQUEST / BAD_REQUEST from VW's auth server usually means
                # the account is rate-limited after a recent auth. Treat as cannot_connect
                # so the user knows to wait and retry rather than change their password.
                if any(
                    word in err_str
                    for word in ("invalid_request", "bad_request", "rate", "too many")
                ):
                    errors["base"] = "cannot_connect"
                elif any(
                    word in err_str
                    for word in ("unauthorized", "401", "403", "credential", "password")
                ):
                    errors["base"] = "invalid_auth"
                else:
                    _LOGGER.exception("Unexpected error connecting to Volkswagen API")
                    errors["base"] = "cannot_connect"
            else:
                self._user_input = user_input
                self._discovered_vehicles = vehicles
                return await self.async_step_select_vehicle()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_select_vehicle(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle vehicle selection step."""
        if not self._discovered_vehicles:
            # No vehicles found — create entry selecting all (empty = all)
            return self._create_entry([])

        if user_input is not None:
            selected_vins = user_input.get(CONF_SELECTED_VINS, [])
            return self._create_entry(selected_vins)

        vehicle_options = [
            SelectOptionDict(
                value=v.vin.value,
                label=f"{v.model.value} ({v.vin.value})"
                if v.model.enabled
                else v.vin.value,
            )
            for v in self._discovered_vehicles
        ]
        all_vins = [v.vin.value for v in self._discovered_vehicles]

        schema = vol.Schema(
            {
                vol.Optional(CONF_SELECTED_VINS, default=all_vins): SelectSelector(
                    SelectSelectorConfig(
                        options=vehicle_options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )

        return self.async_show_form(step_id="select_vehicle", data_schema=schema)

    def _create_entry(self, selected_vins: list[str]) -> ConfigFlowResult:
        """Create the config entry."""
        data = {**self._user_input, CONF_SELECTED_VINS: selected_vins}
        title = self._user_input[CONF_USERNAME]
        return self.async_create_entry(title=title, data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return VolkswagenOptionsFlow()


class VolkswagenOptionsFlow(OptionsFlow):
    """Handle options for an existing Volkswagen config entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_interval = self.config_entry.data.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
