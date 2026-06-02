"""Button platform for ChargeMAX integration."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
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
    """Set up ChargeMAX button entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    api = data["api"]

    entities = []
    for device_sn, coords in coordinators.items():
        device_info = coords["device_info"]
        realtime_coordinator = coords["realtime"]

        entities.extend(
            [
                ChargeMaxRebootButton(realtime_coordinator, device_sn, device_info, api),
                ChargeMaxResetButton(realtime_coordinator, device_sn, device_info, api),
            ]
        )

    async_add_entities(entities)


class ChargeMaxRebootButton(ChargeMaxEntity, ButtonEntity):
    """Reboot button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator, device_sn, device_info, api):
        """Initialize the button."""
        super().__init__(coordinator, device_sn, device_info)
        self._api = api
        self._attr_unique_id = f"{device_sn}_reboot"
        self._attr_name = "Reboot"

    async def async_press(self) -> None:
        """Handle button press."""
        try:
            await self._api.async_reboot(self._device_sn)
            _LOGGER.info("Reboot command sent to device %s", self._device_sn)
        except Exception as err:
            _LOGGER.error("Failed to reboot device: %s", err)
            raise


class ChargeMaxResetButton(ChargeMaxEntity, ButtonEntity):
    """Factory reset button."""

    _attr_icon = "mdi:factory"
    _attr_entity_registry_enabled_default = False  # Disabled by default for safety

    def __init__(self, coordinator, device_sn, device_info, api):
        """Initialize the button."""
        super().__init__(coordinator, device_sn, device_info)
        self._api = api
        self._attr_unique_id = f"{device_sn}_reset"
        self._attr_name = "Factory reset"

    async def async_press(self) -> None:
        """Handle button press."""
        try:
            await self._api.async_reset(self._device_sn)
            _LOGGER.warning("Factory reset command sent to device %s", self._device_sn)
        except Exception as err:
            _LOGGER.error("Failed to reset device: %s", err)
            raise
