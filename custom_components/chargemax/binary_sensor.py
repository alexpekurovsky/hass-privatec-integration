"""Binary sensor platform for ChargeMAX integration."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up ChargeMAX binary sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]

    entities = []
    for device_sn, coords in coordinators.items():
        device_info = coords["device_info"]
        realtime_coordinator = coords["realtime"]

        # All binary sensors use realtime coordinator (10s updates)
        entities.extend(
            [
                ChargeMaxConnectionSensor(realtime_coordinator, device_sn, device_info),
                ChargeMaxCableSensor(realtime_coordinator, device_sn, device_info),
                ChargeMaxFaultSensor(realtime_coordinator, device_sn, device_info),
                ChargeMaxChargingActiveSensor(realtime_coordinator, device_sn, device_info),
            ]
        )

    async_add_entities(entities)


class ChargeMaxConnectionSensor(ChargeMaxEntity, BinarySensorEntity):
    """Connection status binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_connection"
        self._attr_name = "Connection"

    @property
    def is_on(self) -> bool:
        """Return true if device is online."""
        # Device is online if we have recent data and status is not unavailable (7)
        status = self.coordinator.data.get("connecting_status", 7)
        return status != 7


class ChargeMaxCableSensor(ChargeMaxEntity, BinarySensorEntity):
    """Cable connected binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.PLUG

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_cable"
        self._attr_name = "Cable connected"

    @property
    def is_on(self) -> bool:
        """Return true if cable is connected."""
        # Cable is connected if status is >= 2 (connected, charging, completed, paused, reserved)
        status = self.coordinator.data.get("connecting_status", 1)
        return status >= 2 and status != 7  # Exclude unavailable status


class ChargeMaxFaultSensor(ChargeMaxEntity, BinarySensorEntity):
    """Fault status binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_fault"
        self._attr_name = "Fault"

    @property
    def is_on(self) -> bool:
        """Return true if device has a fault."""
        # Fault status is 8
        status = self.coordinator.data.get("connecting_status", 1)
        return status == 8


class ChargeMaxChargingActiveSensor(ChargeMaxEntity, BinarySensorEntity):
    """Charging active binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_charging_active"
        self._attr_name = "Charging active"

    @property
    def is_on(self) -> bool:
        """Return true if actively charging."""
        # Status 3 = charging
        status = self.coordinator.data.get("connecting_status", 1)
        return status == 3
