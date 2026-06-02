"""Switch platform for ChargeMAX integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import ChargeMaxEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ChargeMAX switches."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    api = data["api"]

    entities = []
    for device_sn, coords in coordinators.items():
        device_info = coords["device_info"]
        realtime_coordinator = coords["realtime"]

        entities.append(
            ChargeMaxChargingSwitch(realtime_coordinator, device_sn, device_info, api)
        )

    async_add_entities(entities)


class ChargeMaxChargingSwitch(ChargeMaxEntity, SwitchEntity):
    """Charging control switch."""

    _attr_icon = "mdi:ev-station"

    def __init__(self, coordinator, device_sn, device_info, api):
        """Initialize the switch."""
        super().__init__(coordinator, device_sn, device_info)
        self._api = api
        self._attr_unique_id = f"{device_sn}_charging"
        self._attr_name = "Charging"

    @property
    def is_on(self) -> bool:
        """Return true if charging is active."""
        status = self.coordinator.data.get("connecting_status", 1)
        return status == 3  # 3 = charging

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Only available if cable is connected (status >= 2, excluding unavailable/fault)
        if not super().available:
            return False
        status = self.coordinator.data.get("connecting_status", 1)
        return status >= 2 and status not in [7, 8]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start charging."""
        try:
            await self._api.async_start_charging(self._device_sn)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to start charging: %s", err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop charging."""
        try:
            await self._api.async_stop_charging(self._device_sn)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to stop charging: %s", err)
            raise
