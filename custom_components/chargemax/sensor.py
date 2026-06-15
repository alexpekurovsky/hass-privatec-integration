"""Sensor platform for ChargeMAX integration."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CONNECTING_STATUS_MAP,
    DOMAIN,
    WORK_MODE_MAP,
)
from .entity import ChargeMaxEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ChargeMAX sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]

    entities = []
    for device_sn, coords in coordinators.items():
        device_info = coords["device_info"]
        realtime_coordinator = coords["realtime"]
        medium_coordinator = coords["medium"]
        slow_coordinator = coords["slow"]

        # Realtime sensors (10s updates)
        entities.extend(
            [
                ChargeMaxPowerSensor(realtime_coordinator, device_sn, device_info),
                ChargeMaxVoltageSensor(
                    realtime_coordinator, device_sn, device_info, "L1", "charging_voltage"
                ),
                ChargeMaxVoltageSensor(
                    realtime_coordinator, device_sn, device_info, "L2", "charging_voltage_b"
                ),
                ChargeMaxVoltageSensor(
                    realtime_coordinator, device_sn, device_info, "L3", "charging_voltage_c"
                ),
                ChargeMaxCurrentSensor(
                    realtime_coordinator, device_sn, device_info, "L1", "charging_current"
                ),
                ChargeMaxCurrentSensor(
                    realtime_coordinator, device_sn, device_info, "L2", "charging_current_b"
                ),
                ChargeMaxCurrentSensor(
                    realtime_coordinator, device_sn, device_info, "L3", "charging_current_c"
                ),
                ChargeMaxSessionEnergySensor(realtime_coordinator, device_sn, device_info),
                ChargeMaxStatusSensor(realtime_coordinator, device_sn, device_info),
                ChargeMaxChargingDurationSensor(realtime_coordinator, device_sn, device_info),
                ChargeMaxSOCSensor(realtime_coordinator, device_sn, device_info),
                ChargeMaxCurrentSettingSensor(realtime_coordinator, device_sn, device_info),
            ]
        )

        # Medium frequency sensors (5min updates)
        entities.extend(
            [
                ChargeMaxTotalEnergySensor(medium_coordinator, device_sn, device_info),
                ChargeMaxTotalSessionsSensor(medium_coordinator, device_sn, device_info),
                ChargeMaxTotalTimeSensor(medium_coordinator, device_sn, device_info),
                ChargeMaxLastActivitySensor(medium_coordinator, device_sn, device_info),
            ]
        )

        # Slow frequency sensors (1h updates)
        entities.extend(
            [
                ChargeMaxWorkModeSensor(slow_coordinator, device_sn, device_info),
                ChargeMaxFirmwareSensor(slow_coordinator, device_sn, device_info),
            ]
        )

    async_add_entities(entities)


class ChargeMaxPowerSensor(ChargeMaxEntity, SensorEntity):
    """Charging power sensor."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_power"
        self._attr_name = "Charging power"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        # Power is in 0.1W units (e.g., 34200 = 3420.0W)
        power = self.coordinator.data.get("charging_power", 0)
        return round(power / 10, 1) if power else 0


class ChargeMaxVoltageSensor(ChargeMaxEntity, SensorEntity):
    """Voltage sensor for each phase."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    def __init__(self, coordinator, device_sn, device_info, phase, data_key):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._phase = phase
        self._data_key = data_key
        self._attr_unique_id = f"{device_sn}_voltage_{phase.lower()}"
        self._attr_name = f"Voltage {phase}"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        # Voltage is in 0.1V units (e.g., 2338 = 233.8V)
        voltage = self.coordinator.data.get(self._data_key, 0)
        return round(voltage / 10, 1) if voltage else 0


class ChargeMaxCurrentSensor(ChargeMaxEntity, SensorEntity):
    """Current sensor for each phase."""

    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(self, coordinator, device_sn, device_info, phase, data_key):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._phase = phase
        self._data_key = data_key
        self._attr_unique_id = f"{device_sn}_current_{phase.lower()}"
        self._attr_name = f"Current {phase}"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        # Current is in 0.1A units (e.g., 160 = 16.0A)
        current = self.coordinator.data.get(self._data_key, 0)
        return round(current / 10, 1) if current else 0


class ChargeMaxSessionEnergySensor(ChargeMaxEntity, SensorEntity):
    """Session energy sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_session_energy"
        self._attr_name = "Session energy"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        # Energy is in Wh, convert to kWh
        # API field is "charged_electricity" not "ele_quantity"
        energy_wh = self.coordinator.data.get("charged_electricity", 0)
        return round(energy_wh / 1000, 3) if energy_wh else 0


class ChargeMaxStatusSensor(ChargeMaxEntity, SensorEntity):
    """Charging status sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(CONNECTING_STATUS_MAP.values())

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_status"
        self._attr_name = "Status"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        status_code = self.coordinator.data.get("connecting_status", 1)
        return CONNECTING_STATUS_MAP.get(status_code)


class ChargeMaxChargingDurationSensor(ChargeMaxEntity, SensorEntity):
    """Charging duration sensor."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_charging_duration"
        self._attr_name = "Charging duration"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.coordinator.data.get("charging_time", 0)


class ChargeMaxSOCSensor(ChargeMaxEntity, SensorEntity):
    """State of charge sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_soc"
        self._attr_name = "State of charge"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        # API field is "soc" not "battery_soc"
        return self.coordinator.data.get("soc", 0)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Only available if soc is present and > 0
        return (
            super().available
            and self.coordinator.data.get("soc", 0) > 0
        )


class ChargeMaxCurrentSettingSensor(ChargeMaxEntity, SensorEntity):
    """Current setting sensor."""

    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_current_setting"
        self._attr_name = "Current setting"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.coordinator.data.get("setting_current", 0)


class ChargeMaxLastActivitySensor(ChargeMaxEntity, SensorEntity):
    """Last activity timestamp sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_last_activity"
        self._attr_name = "Last activity"

    @property
    def native_value(self) -> datetime | None:
        """Return the state."""
        # Get from device_info (from devices list API)
        device_info = self.coordinator.data.get("device_info", {})
        timestamp = device_info.get("lastActivityTime", 0)
        if timestamp:
            # Timestamp is already in seconds, not milliseconds
            return datetime.fromtimestamp(timestamp)
        return None


class ChargeMaxTotalEnergySensor(ChargeMaxEntity, SensorEntity):
    """Total energy sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_total_energy"
        self._attr_name = "Total energy"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        statistics = self.coordinator.data.get("statistics", {})
        # API returns Statistics array, get first element
        stats_list = statistics.get("Statistics", [])
        if stats_list and len(stats_list) > 0:
            return stats_list[0].get("totalElec", 0)
        return 0

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        return {
            "last_reset": None,  # Never resets - lifetime counter
        }


class ChargeMaxTotalSessionsSensor(ChargeMaxEntity, SensorEntity):
    """Total sessions sensor."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_total_sessions"
        self._attr_name = "Total sessions"
        self._attr_icon = "mdi:counter"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        statistics = self.coordinator.data.get("statistics", {})
        # API returns Statistics array, get first element
        stats_list = statistics.get("Statistics", [])
        if stats_list and len(stats_list) > 0:
            return stats_list[0].get("totalOrderNum", 0)
        return 0


class ChargeMaxTotalTimeSensor(ChargeMaxEntity, SensorEntity):
    """Total charging time sensor."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfTime.HOURS

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_total_time"
        self._attr_name = "Total charging time"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        statistics = self.coordinator.data.get("statistics", {})
        # API returns Statistics array, get first element
        stats_list = statistics.get("Statistics", [])
        if stats_list and len(stats_list) > 0:
            # totalChargingTime is a string in seconds
            total_seconds = int(stats_list[0].get("totalChargingTime", "0"))
            return round(total_seconds / 3600, 1) if total_seconds else 0
        return 0


class ChargeMaxWorkModeSensor(ChargeMaxEntity, SensorEntity):
    """Work mode sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(WORK_MODE_MAP.values())

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_work_mode_sensor"
        self._attr_name = "Work mode"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        work_mode_data = self.coordinator.data.get("work_mode", {})
        mode_code = work_mode_data.get("work_mode", 0)
        return WORK_MODE_MAP.get(mode_code)


class ChargeMaxFirmwareSensor(ChargeMaxEntity, SensorEntity):
    """Firmware version sensor."""

    def __init__(self, coordinator, device_sn, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator, device_sn, device_info)
        self._attr_unique_id = f"{device_sn}_firmware"
        self._attr_name = "Firmware version"
        self._attr_icon = "mdi:chip"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        device_info = self.coordinator.data.get("device_info", {})
        firmware = device_info.get("firmware_version", 0)

        if firmware > 0:
            return f"v{firmware // 1000000}.{(firmware // 1000) % 1000}.{firmware % 1000}"
        return "Unknown"
