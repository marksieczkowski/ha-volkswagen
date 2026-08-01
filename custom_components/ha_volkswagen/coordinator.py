"""DataUpdateCoordinator for the HA Volkswagen integration."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import jwt
from carconnectivity import carconnectivity as cc
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_COUNTRY,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SELECTED_VINS,
    CONF_SPIN,
    CONF_UNIT_SYSTEM,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_SYSTEM,
    DOMAIN,
    TOKENSTORE_FILENAME_TEMPLATE,
    UNIT_SYSTEM_IMPERIAL,
)

if TYPE_CHECKING:
    from carconnectivity.garage import Garage
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    type VolkswagenConfigEntry = ConfigEntry[VolkswagenDataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)

CONNECTOR_TYPE = "volkswagen_na"


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
                    "type": CONNECTOR_TYPE,
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


class VolkswagenDataUpdateCoordinator(DataUpdateCoordinator["Garage"]):
    """Coordinator that owns a CarConnectivity instance and drives polling."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialise the coordinator."""
        self.car_connectivity: cc.CarConnectivity | None = None

        # Options (set via the options flow) take precedence over the original
        # setup data — otherwise changing the poll interval would have no effect.
        merged = {**config_entry.data, **config_entry.options}
        scan_interval = merged.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
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
        config_dict = build_carconnectivity_config(
            {**self.config_entry.data, **self.config_entry.options}
        )
        tokenstore_path = get_tokenstore_path(
            self.hass.config.config_dir, self.config_entry.entry_id
        )

        def _startup_sync() -> cc.CarConnectivity:
            # Do NOT call instance.startup() — that spawns a background polling
            # thread inside the connector that would race our executor-based
            # fetch_all() calls and cause 400 errors from the VW auth endpoint.
            # The HA DataUpdateCoordinator is our sole polling driver.
            return cc.CarConnectivity(
                config=config_dict,
                tokenstore_file=tokenstore_path,
            )

        self.car_connectivity = await self.hass.async_add_executor_job(_startup_sync)

    def _connector_registry(self) -> dict:
        """Return the CarConnectivity connector registry, or {} if unavailable."""
        connectors = getattr(self.car_connectivity, "connectors", None)
        registry = getattr(connectors, "connectors", None)
        return registry if isinstance(registry, dict) else {}

    def _connector_session(self) -> Any | None:
        """Return the VW connector's HTTP session, or None if unavailable."""
        connector = self._connector_registry().get(CONNECTOR_TYPE)
        return getattr(connector, "session", None)

    def _persist_all(self) -> None:
        """Persist connector sessions, then the tokenstore itself.

        CarConnectivity.persist() only serialises its tokenstore dict to disk;
        that dict is filled by each connector's persist() (which delegates to
        SessionManager). Upstream chains the two inside shutdown(), which we
        never call — so calling CarConnectivity.persist() alone always writes
        an empty tokenstore, meaning the file never appears and every restart
        performs a full login against a rate-limited endpoint.
        """
        for connector in self._connector_registry().values():
            try:
                connector.persist()
            except Exception:
                _LOGGER.debug("Could not persist connector session", exc_info=True)
        self.car_connectivity.persist()

    def _align_session_user_id(self) -> None:
        """Point the connector session at the Car-Net account userId.

        The connector takes session.user_id from the identity provider's login
        redirect, which is the SSO id (the token's `ssoid` claim). VW's Car-Net
        backend instead expects the account userId — the `sub` claim — in every
        user-scoped path (/rrs/v1/privileges/user/..., /ss/v1/user/...) and in
        the x-user-id header, and answers 403 USER_NOT_AUTHORIZED otherwise.
        Only /account/v1/garage works with the wrong id, which is why login
        looks healthy while every vehicle call fails.

        Upstream bug, present in connector 0.1.24:
        https://github.com/zackcornelius/CarConnectivity-connector-volkswagen-na/issues/83
        The assignment is conditional, so it becomes a no-op once upstream
        supplies the right id — safe to keep across connector upgrades.

        Best effort by design: any failure here is logged and ignored, because
        the fetch_all() that follows will surface the real error properly.
        """
        session = self._connector_session()
        if session is None:
            return

        try:
            token = session.token
            # token is None before the first login, a dict afterwards; anything
            # else means the session is not shaped as we expect, so leave it be.
            if token is not None and not isinstance(token, dict):
                return
            if not token or not token.get("access_token"):
                # Cold start with no tokenstore: fetch_all() would log in and
                # immediately use the wrong id, so log in and realign first.
                session.login()
                token = session.token
            if not isinstance(token, dict):
                return
            access_token = token.get("access_token")
            if not access_token:
                return
            claims = jwt.decode(access_token, options={"verify_signature": False})
        except Exception:
            _LOGGER.debug("Could not realign VW session user id", exc_info=True)
            return

        sub = claims.get("sub")
        if sub and session.user_id != sub:
            _LOGGER.debug("Realigning VW session user id to the account userId")
            session.user_id = sub

    def _fetch_all_sync(self) -> Garage:
        """Blocking fetch — runs in the executor thread."""
        if self.car_connectivity is None:
            raise UpdateFailed("CarConnectivity not initialised")
        # Must run before every fetch: user_id lives in session.metadata and is
        # reset by each full login, not just the first one.
        self._align_session_user_id()
        self.car_connectivity.fetch_all()
        self._persist_all()
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
            if any(
                word in err_str
                for word in ("auth", "unauthorized", "401", "403", "token")
            ):
                raise ConfigEntryAuthFailed(
                    f"Authentication failed for Volkswagen account: {err}"
                ) from err
            raise UpdateFailed(
                f"Error communicating with Volkswagen API: {err}"
            ) from err

    @property
    def is_imperial(self) -> bool:
        """Return True if imperial units are configured.

        Options take precedence over data (options flow overwrites options,
        not data; data holds the original setup values).
        """
        unit_system = self.config_entry.options.get(
            CONF_UNIT_SYSTEM,
            self.config_entry.data.get(CONF_UNIT_SYSTEM, DEFAULT_UNIT_SYSTEM),
        )
        return unit_system == UNIT_SYSTEM_IMPERIAL

    def get_vehicles(self) -> list:
        """Return vehicles, optionally filtered to the user's selected VINs."""
        if self.data is None:
            return []
        all_vehicles = list(self.data.list_vehicles())
        selected = self.config_entry.data.get(CONF_SELECTED_VINS, [])
        if not selected:
            return all_vehicles
        return [v for v in all_vehicles if v.vin.value in selected]

    async def async_refresh_after_command(self) -> None:
        """Schedule refreshes at 20 s, 60 s, and 120 s after a command.

        The VW NA API typically takes 15-60 s to reflect a command result, so an
        immediate refresh would return stale data and cause state churn in HA.
        """
        for delay in (20, 60, 120):
            # Background tasks tied to the config entry are cancelled on unload.
            self.config_entry.async_create_background_task(
                self.hass,
                self._delayed_refresh(delay),
                name=f"{DOMAIN}_refresh_after_command_{delay}s",
            )

    async def _delayed_refresh(self, delay: int) -> None:
        await asyncio.sleep(delay)
        await self.async_request_refresh()

    async def async_shutdown(self) -> None:
        """Persist tokens and release the CarConnectivity instance."""
        if self.car_connectivity is not None:
            # We never called startup() so we should not call shutdown() either
            # (it would try to join the non-existent background thread).
            # Persist tokens manually so the next startup can reuse them.
            await self.hass.async_add_executor_job(self._persist_all)
            self.car_connectivity = None
