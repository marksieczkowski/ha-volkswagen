"""Constants for the HA Volkswagen integration."""
from __future__ import annotations

DOMAIN = "ha_volkswagen"

PLATFORMS = [
    "sensor",
    "binary_sensor",
    "device_tracker",
    "lock",
    "climate",
    "switch",
]

# Config entry data keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_COUNTRY = "country"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SELECTED_VINS = "selected_vins"
CONF_SPIN = "spin"

# Defaults
DEFAULT_SCAN_INTERVAL = 300  # seconds (5 minutes)
MIN_SCAN_INTERVAL = 180  # carconnectivity NA API enforced minimum (3 minutes)
DEFAULT_COUNTRY = "us"
SUPPORTED_COUNTRIES = ["us", "ca"]

# Tokenstore filename template — stored in hass.config.config_dir/.storage/
TOKENSTORE_FILENAME_TEMPLATE = "ha_volkswagen_{entry_id}_tokenstore"
