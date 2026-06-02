"""Data update coordinators for ChargeMAX integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ChargeMaxAPI, ChargeMaxAuthError, ChargeMaxConnectionError
from .const import (
    DOMAIN,
    UPDATE_INTERVAL_REALTIME,
    UPDATE_INTERVAL_MEDIUM,
    UPDATE_INTERVAL_SLOW,
)

_LOGGER = logging.getLogger(__name__)


class ChargeMaxRealtimeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for real-time device data (10s updates)."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: ChargeMaxAPI,
        device_sn: str,
        device_id: str,
    ) -> None:
        """Initialize coordinator."""
        self.api = api
        self.device_sn = device_sn
        self.device_id = device_id

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_realtime_{device_sn}",
            update_interval=UPDATE_INTERVAL_REALTIME,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            data = await self.api.async_get_device_info(self.device_sn)
            _LOGGER.debug(
                "Realtime data updated for %s: status=%s, power=%s",
                self.device_sn,
                data.get("connecting_status"),
                data.get("charging_power"),
            )
            return data
        except ChargeMaxAuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except ChargeMaxConnectionError as err:
            raise UpdateFailed(f"Connection failed: {err}") from err


class ChargeMaxMediumCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for medium-frequency data (5min updates)."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: ChargeMaxAPI,
        device_sn: str,
        device_id: str,
    ) -> None:
        """Initialize coordinator."""
        self.api = api
        self.device_sn = device_sn
        self.device_id = device_id

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_medium_{device_sn}",
            update_interval=UPDATE_INTERVAL_MEDIUM,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            # Get statistics and device list
            statistics = await self.api.async_get_order_statistics()
            devices = await self.api.async_get_devices()

            # Find this device in the list
            device_info = None
            if devices and "evse_infos" in devices:
                for device in devices["evse_infos"]:
                    if device["sn"] == self.device_sn:
                        device_info = device
                        break

            _LOGGER.debug("Medium data updated for %s", self.device_sn)

            return {
                "statistics": statistics,
                "device_info": device_info,
            }
        except ChargeMaxAuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except ChargeMaxConnectionError as err:
            raise UpdateFailed(f"Connection failed: {err}") from err


class ChargeMaxSlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for slow-frequency data (1h updates)."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: ChargeMaxAPI,
        device_sn: str,
        device_id: str,
    ) -> None:
        """Initialize coordinator."""
        self.api = api
        self.device_sn = device_sn
        self.device_id = device_id

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_slow_{device_sn}",
            update_interval=UPDATE_INTERVAL_SLOW,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            # Get work mode and device list
            work_mode = await self.api.async_get_work_mode(self.device_sn)
            devices = await self.api.async_get_devices()

            # Find this device in the list for firmware info
            device_info = None
            if devices and "evse_infos" in devices:
                for device in devices["evse_infos"]:
                    if device["sn"] == self.device_sn:
                        device_info = device
                        break

            _LOGGER.debug("Slow data updated for %s", self.device_sn)

            return {
                "work_mode": work_mode,
                "device_info": device_info,
            }
        except ChargeMaxAuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except ChargeMaxConnectionError as err:
            raise UpdateFailed(f"Connection failed: {err}") from err
