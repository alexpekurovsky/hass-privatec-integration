"""The ChargeMAX integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import ChargeMaxAPI, ChargeMaxAuthError, ChargeMaxConnectionError
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN
from .coordinator import (
    ChargeMaxRealtimeCoordinator,
    ChargeMaxMediumCoordinator,
    ChargeMaxSlowCoordinator,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ChargeMAX from a config entry."""
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    # Create API client
    api = ChargeMaxAPI(hass)

    # Attempt login
    try:
        await api.async_login(email, password)
    except ChargeMaxAuthError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except ChargeMaxConnectionError as err:
        raise ConfigEntryNotReady(f"Connection failed: {err}") from err

    # Get devices
    try:
        devices = await api.async_get_devices()
    except ChargeMaxConnectionError as err:
        raise ConfigEntryNotReady(f"Failed to fetch devices: {err}") from err

    if not devices or "evse_infos" not in devices or not devices["evse_infos"]:
        _LOGGER.error("No devices found in account")
        return False

    # Create coordinators for each device
    coordinators = {}
    for device in devices["evse_infos"]:
        device_sn = device["sn"]
        device_id = device["evseId"]

        coordinators[device_sn] = {
            "realtime": ChargeMaxRealtimeCoordinator(hass, api, device_sn, device_id),
            "medium": ChargeMaxMediumCoordinator(hass, api, device_sn, device_id),
            "slow": ChargeMaxSlowCoordinator(hass, api, device_sn, device_id),
            "device_info": device,  # Store initial device info
        }

        # Initial data fetch
        await coordinators[device_sn]["realtime"].async_config_entry_first_refresh()
        await coordinators[device_sn]["medium"].async_config_entry_first_refresh()
        await coordinators[device_sn]["slow"].async_config_entry_first_refresh()

    # Store coordinators and API
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinators": coordinators,
    }

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
