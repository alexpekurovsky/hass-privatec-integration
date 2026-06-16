"""ChargeMAX API client."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_BASE_URL, API_V2_BASE_URL, API_HEADERS

_LOGGER = logging.getLogger(__name__)


class ChargeMaxAuthError(Exception):
    """Exception for authentication errors."""


class ChargeMaxConnectionError(Exception):
    """Exception for connection errors."""


class ChargeMaxAPI:
    """ChargeMAX API client."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the API client."""
        self.hass = hass
        self.session = async_get_clientsession(hass)
        self.base_url = API_BASE_URL
        self.token: str | None = None

    async def async_login(self, email: str, password: str) -> bool:
        """Login with email and password."""
        # Get timezone offset as integer (hours)
        tz_offset_seconds = time.timezone if not time.daylight else time.altzone
        zone = int(-tz_offset_seconds / 3600)

        # Normalize email
        email = email.lower().strip()

        # Create login data
        login_data = {
            "login_type": 0,
            "name": email,
            "passwd": password,
            "zone": zone,
        }

        # JSON must be compact for signature
        data_str = json.dumps(login_data, separators=(",", ":"))
        timestamp = int(time.time() * 1000)

        # Sign: MD5(timestamp + data + "chargingc")
        sign_str = str(timestamp) + data_str + "chargingc"
        sign = hashlib.md5(sign_str.encode()).hexdigest()

        # Final payload
        payload = {
            "uid": "",
            "data": data_str,
            "timestamp": timestamp,
            "sign": sign,
        }

        # Headers
        headers = {
            **API_HEADERS,
            "token": "",
        }

        url = f"{self.base_url}/user/login"

        try:
            async with self.session.post(
                url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    raise ChargeMaxConnectionError(f"HTTP {response.status}")

                data = await response.json()

                if data.get("ret") == 200:
                    response_data = json.loads(data.get("data", "{}"))
                    self.token = response_data.get("token")
                    if self.token:
                        _LOGGER.debug("Login successful")
                        return True

                if data.get("ret") == 5:
                    raise ChargeMaxAuthError("User not found or invalid credentials")

                raise ChargeMaxAuthError(
                    f"Login failed: ret={data.get('ret')}, msg={data.get('msg')}"
                )

        except asyncio.TimeoutError as err:
            raise ChargeMaxConnectionError("Request timeout") from err
        except aiohttp.ClientError as err:
            raise ChargeMaxConnectionError(f"Connection error: {err}") from err

    async def _make_authenticated_request(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        use_api_v2: bool = False,
    ) -> dict[str, Any]:
        """Make an authenticated API request with proper signing."""
        if not self.token:
            raise ChargeMaxAuthError("Not logged in")

        # API v2 uses different base URL and simpler auth
        if use_api_v2:
            base_url = API_V2_BASE_URL
            url = f"{base_url}{endpoint}"

            headers = {
                **API_HEADERS,
                "Authorization": self.token,
            }

            try:
                async with self.session.post(
                    url,
                    json=data if data else {},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 401:
                        raise ChargeMaxAuthError("Token expired or invalid")
                    if response.status != 200:
                        raise ChargeMaxConnectionError(f"HTTP {response.status}")

                    result = await response.json()
                    return result

            except asyncio.TimeoutError as err:
                raise ChargeMaxConnectionError("Request timeout") from err
            except aiohttp.ClientError as err:
                raise ChargeMaxConnectionError(f"Connection error: {err}") from err

        # API v1 uses signing
        request_data = data if data else {}
        data_str = json.dumps(request_data, separators=(",", ":"))
        timestamp = int(time.time() * 1000)

        # Sign request
        sign_str = str(timestamp) + data_str + "chargingc"
        sign = hashlib.md5(sign_str.encode()).hexdigest()

        payload = {
            "uid": "",
            "data": data_str,
            "timestamp": timestamp,
            "sign": sign,
        }

        headers = {
            **API_HEADERS,
            "token": self.token,
        }

        url = f"{self.base_url}{endpoint}"

        try:
            async with self.session.post(
                url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 401:
                    raise ChargeMaxAuthError("Token expired or invalid")
                if response.status != 200:
                    raise ChargeMaxConnectionError(f"HTTP {response.status}")

                result = await response.json()

                if result.get("ret") == 200:
                    return json.loads(result.get("data", "{}"))

                if result.get("ret") == 401:
                    raise ChargeMaxAuthError("Token expired")

                raise ChargeMaxConnectionError(
                    f"API error: ret={result.get('ret')}, msg={result.get('msg')}"
                )

        except asyncio.TimeoutError as err:
            raise ChargeMaxConnectionError("Request timeout") from err
        except aiohttp.ClientError as err:
            raise ChargeMaxConnectionError(f"Connection error: {err}") from err

    async def async_get_devices(self) -> dict[str, Any]:
        """Get list of user's charging stations."""
        return await self._make_authenticated_request("/user/evses")

    async def async_get_device_info(self, sn: str) -> dict[str, Any]:
        """Get real-time charging info for a device."""
        return await self._make_authenticated_request("/evse/info", {"sn": sn})

    async def async_get_charging_history(
        self,
        evse_id: str | None = None,
        page: int = 1,
        limit: int = 100,
        state_filter: int = 3,
        order_type: int = 1,
    ) -> dict[str, Any]:
        """Get charging history/records."""
        data: dict[str, Any] = {
            "pageReq": {"page": page, "limit": limit},
            "absolute": True,
            "stateFilter": state_filter,
            "orderType": order_type,
        }

        if evse_id:
            data["evseId"] = evse_id

        return await self._make_authenticated_request(
            "/user/order/list", data, use_api_v2=True
        )

    async def async_get_order_statistics(
        self,
        evse_id: str | None = None,
        user_id: str | None = None,
        start_time: str | None = None,
        stop_time: str | None = None,
        grain: int = 30,
    ) -> dict[str, Any]:
        """Get order statistics.

        Args:
            evse_id: Device ID to filter by
            user_id: User ID
            start_time: Start datetime in format "YYYY-MM-DD HH:mm:ss"
            stop_time: Stop datetime in format "YYYY-MM-DD HH:mm:ss"
            grain: Granularity (30 = monthly statistics)

        Returns monthly statistics if start_time/stop_time provided,
        otherwise returns total statistics.
        """
        data: dict[str, Any] = {}

        if start_time and stop_time:
            # Request detailed statistics with date range
            data = {
                "grain": grain,
                "startTime": start_time,
                "stopTime": stop_time,
            }
            if evse_id:
                data["evseId"] = evse_id
            if user_id:
                data["userId"] = user_id

        return await self._make_authenticated_request(
            "/user/order/statistics", data, use_api_v2=True
        )

    async def async_get_work_mode(self, sn: str) -> dict[str, Any]:
        """Get work mode."""
        return await self._make_authenticated_request("/evse/get_work_mode", {"sn": sn})

    async def async_start_charging(self, sn: str, current: int) -> dict[str, Any]:
        """Start charging."""
        return await self._make_authenticated_request(
            "/evse/start", {"sn": sn, "charge_type": 0, "charging_current": current}
        )

    async def async_stop_charging(self, sn: str) -> dict[str, Any]:
        """Stop charging."""
        return await self._make_authenticated_request("/evse/stop", {"sn": sn})

    async def async_set_current(self, sn: str, current: int) -> dict[str, Any]:
        """Set charging current."""
        return await self._make_authenticated_request(
            "/evse/set_current", {"sn": sn, "charging_current": current}
        )

    async def async_set_work_mode(self, sn: str, mode: int) -> dict[str, Any]:
        """Set work mode."""
        return await self._make_authenticated_request(
            "/evse/set_work_mode", {"sn": sn, "work_mode": mode}
        )

    async def async_reboot(self, sn: str) -> dict[str, Any]:
        """Reboot device."""
        return await self._make_authenticated_request("/evse/reboot", {"sn": sn})

    async def async_reset(self, sn: str) -> dict[str, Any]:
        """Factory reset device."""
        return await self._make_authenticated_request("/evse/reset", {"sn": sn})
