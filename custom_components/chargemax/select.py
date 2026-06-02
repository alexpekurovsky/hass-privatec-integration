"""Select platform for ChargeMAX integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, WORK_MODE_MAP
from .entity import ChargeMaxEntity

_LOGGER = logging.getLogger(__name__)

# Reverse map for work mode names to codes
WORK_MODE_REVERSE_MAP = {v: k for k, v in WORK_MODE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ChargeMAX select entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    api = data["api"]

    entities = []
    for device_sn, coords in coordinators.items():
        device_info = coords["device_info"]
        slow_coordinator = coords["slow"]

        entities.append(
            ChargeMaxWorkModeSelect(slow_coordinator, device_sn, device_info, api)
        )

    async_add_entities(entities)


class ChargeMaxWorkModeSelect(ChargeMaxEntity, SelectEntity):
    """Work mode select entity."""

    _attr_icon = "mdi:cog"
    _attr_options = list(WORK_MODE_MAP.values())

    def __init__(self, coordinator, device_sn, device_info, api):
        """Initialize the select entity."""
        super().__init__(coordinator, device_sn, device_info)
        self._api = api
        self._attr_unique_id = f"{device_sn}_work_mode"
        self._attr_name = "Work mode"

    @property
    def current_option(self) -> str | None:
        """Return the current work mode."""
        work_mode_data = self.coordinator.data.get("work_mode", {})
        mode_code = work_mode_data.get("work_mode", 0)
        return WORK_MODE_MAP.get(mode_code, "unknown")

    async def async_select_option(self, option: str) -> None:
        """Change the work mode."""
        mode_code = WORK_MODE_REVERSE_MAP.get(option)
        if mode_code is None:
            _LOGGER.error("Invalid work mode: %s", option)
            return

        try:
            await self._api.async_set_work_mode(self._device_sn, mode_code)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set work mode: %s", err)
            raise
