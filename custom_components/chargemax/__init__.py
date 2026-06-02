"""The ChargeMAX integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .api import ChargeMaxAPI, ChargeMaxAuthError, ChargeMaxConnectionError
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN
from .coordinator import (
    ChargeMaxRealtimeCoordinator,
    ChargeMaxMediumCoordinator,
    ChargeMaxSlowCoordinator,
)
from .statistics import async_import_charging_history

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

    # Schedule initial history import for all devices (after 30s delay to not block startup)
    async def async_do_initial_import():
        """Import history for all devices on first setup."""
        await asyncio.sleep(30)  # Wait for startup to complete

        for device_sn, coords in coordinators.items():
            device_id = coords["device_info"]["evseId"]
            _LOGGER.info("Starting initial history import for device %s", device_sn)

            try:
                result = await async_import_charging_history(hass, api, device_sn, device_id)
                _LOGGER.info(
                    "Initial import complete for %s: %d sessions, %.3f kWh",
                    device_sn,
                    result["sessions_imported"],
                    result["total_energy"],
                )
            except Exception as err:
                _LOGGER.error("Failed initial history import for %s: %s", device_sn, err)

    # Start background import task
    hass.async_create_task(async_do_initial_import())

    # Schedule hourly history checks
    async def async_hourly_import(now):
        """Import new history every hour."""
        for device_sn, coords in coordinators.items():
            device_id = coords["device_info"]["evseId"]

            try:
                result = await async_import_charging_history(hass, api, device_sn, device_id)

                if result["sessions_imported"] > 0:
                    _LOGGER.info(
                        "Hourly import for %s: %d new sessions, %.3f kWh",
                        device_sn,
                        result["sessions_imported"],
                        result["total_energy"],
                    )
                else:
                    _LOGGER.debug("Hourly import for %s: no new sessions", device_sn)

            except Exception as err:
                _LOGGER.error("Failed hourly history import for %s: %s", device_sn, err)

    # Register hourly task
    async_track_time_interval(hass, async_hourly_import, timedelta(hours=1))

    # Register services
    async def handle_import_history(call):
        """Handle the import_history service call."""
        device_id = call.data.get("device_id")

        # Find the device by device_id (registry ID)
        import homeassistant.helpers.device_registry as dr
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get(device_id)

        if not device_entry:
            _LOGGER.error("Device not found: %s", device_id)
            return

        # Find device serial number from identifiers
        device_sn = None
        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                device_sn = identifier[1]
                break

        if not device_sn:
            _LOGGER.error("Could not find serial number for device %s", device_id)
            return

        # Find the coordinator for this device
        coords = None
        evse_id = None
        for sn, coord_data in coordinators.items():
            if sn == device_sn:
                coords = coord_data
                evse_id = coord_data["device_info"]["evseId"]
                break

        if not coords or not evse_id:
            _LOGGER.error("Could not find device data for %s", device_sn)
            return

        # Import history
        _LOGGER.info("Importing charging history for device %s (SN: %s)", device_id, device_sn)
        result = await async_import_charging_history(hass, api, device_sn, evse_id)

        _LOGGER.info(
            "History import complete: %d sessions, %.3f kWh, %s",
            result["sessions_imported"],
            result["total_energy"],
            result.get("date_range", "no date range"),
        )

    # Register service only once (check if not already registered)
    if not hass.services.has_service(DOMAIN, "import_history"):
        hass.services.async_register(DOMAIN, "import_history", handle_import_history)

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
