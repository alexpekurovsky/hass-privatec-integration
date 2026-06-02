"""Constants for the ChargeMAX integration."""
from datetime import timedelta
from typing import Final

# Integration domain
DOMAIN: Final = "chargemax"

# Configuration
CONF_EMAIL: Final = "email"
CONF_PASSWORD: Final = "password"

# API endpoints
API_BASE_URL: Final = "https://user.chargingc.com/privatec/v1.0"
API_V2_BASE_URL: Final = "https://user.chargingc.com"

# API headers
API_HEADERS: Final = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "appid": "__UNI__1606087",
    "channel": "2",
    "client": "ChargeMAX",
    "language": "en",
    "client_version": "1.9.3",
    "platform": "android",
}

# Update intervals
UPDATE_INTERVAL_REALTIME: Final = timedelta(seconds=10)
UPDATE_INTERVAL_MEDIUM: Final = timedelta(minutes=5)
UPDATE_INTERVAL_SLOW: Final = timedelta(hours=1)

# Device info
MANUFACTURER: Final = "ChargeMax"
MODEL_PREFIX: Final = "ChargeMAX"

# Connecting status constants
CONNECTING_STATUS_IDLE: Final = 1
CONNECTING_STATUS_CONNECTED: Final = 2
CONNECTING_STATUS_CHARGING: Final = 3
CONNECTING_STATUS_COMPLETED: Final = 4
CONNECTING_STATUS_PAUSED: Final = 5
CONNECTING_STATUS_RESERVED: Final = 6
CONNECTING_STATUS_UNAVAILABLE: Final = 7
CONNECTING_STATUS_FAULT: Final = 8

CONNECTING_STATUS_MAP: Final = {
    CONNECTING_STATUS_IDLE: "idle",
    CONNECTING_STATUS_CONNECTED: "connected",
    CONNECTING_STATUS_CHARGING: "charging",
    CONNECTING_STATUS_COMPLETED: "completed",
    CONNECTING_STATUS_PAUSED: "paused",
    CONNECTING_STATUS_RESERVED: "reserved",
    CONNECTING_STATUS_UNAVAILABLE: "unavailable",
    CONNECTING_STATUS_FAULT: "fault",
}

# Work mode constants
WORK_MODE_NORMAL: Final = 0
WORK_MODE_SCHEDULED: Final = 1
WORK_MODE_SMART: Final = 2

WORK_MODE_MAP: Final = {
    WORK_MODE_NORMAL: "Normal",
    WORK_MODE_SCHEDULED: "Scheduled",
    WORK_MODE_SMART: "Smart",
}

# Service names
SERVICE_SET_CHARGING_CURRENT: Final = "set_charging_current"
SERVICE_START_CHARGING: Final = "start_charging"
SERVICE_STOP_CHARGING: Final = "stop_charging"
SERVICE_SET_WORK_MODE: Final = "set_work_mode"

# Attributes
ATTR_CURRENT: Final = "current"
ATTR_MODE: Final = "mode"
ATTR_DEVICE_ID: Final = "device_id"
ATTR_FAULT_CODE: Final = "fault_code"
ATTR_CONNECTING_STATUS: Final = "connecting_status"
ATTR_STATUS_DESC: Final = "status_desc"
ATTR_STATE: Final = "state"
ATTR_MIN_CURRENT: Final = "min_current"
ATTR_MAX_CURRENT: Final = "max_current"
