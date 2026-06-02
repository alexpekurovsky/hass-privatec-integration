"""Number platform for ChargeMAX integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
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
    """Set up ChargeMAX number entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    api = data["api"]

    entities = []
    for device_sn, coords in coordinators.items():
        device_info = coords["device_info"]
        realtime_coordinator = coords["realtime"]

        entities.append(
            ChargeMaxCurrentLimitNumber(realtime_coordinator, device_sn, device_info, api)
        )

    async_add_entities(entities)


class ChargeMaxCurrentLimitNumber(ChargeMaxEntity, NumberEntity):
    """Current limit number entity."""

    _attr_icon = "mdi:current-ac"
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_native_step = 1

    def __init__(self, coordinator, device_sn, device_info, api):
        """Initialize the number entity."""
        super().__init__(coordinator, device_sn, device_info)
        self._api = api
        self._attr_unique_id = f"{device_sn}_current_limit"
        self._attr_name = "Current limit"

        # Get min/max from device info
        self._attr_native_min_value = device_info.get("rated_min_current", 8)
        self._attr_native_max_value = device_info.get("rated_max_current", 32)

    @property
    def native_value(self) -> float:
        """Return the current limit."""
        return self.coordinator.data.get("setting_current", 16)

    async def async_set_native_value(self, value: float) -> None:
        """Set the current limit."""
        try:
            await self._api.async_set_current(self._device_sn, int(value))
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set current limit: %s", err)
            raise
