"""Config flow for ChargeMAX integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ChargeMaxAPI, ChargeMaxAuthError, ChargeMaxConnectionError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    api = ChargeMaxAPI(hass)

    # Test login
    await api.async_login(data[CONF_EMAIL], data[CONF_PASSWORD])

    # Get devices
    devices = await api.async_get_devices()

    if not devices or "evse_infos" not in devices or not devices["evse_infos"]:
        raise NoDevicesError("No devices found in account")

    # Return info
    return {
        "title": f"ChargeMAX ({data[CONF_EMAIL]})",
        "devices": devices["evse_infos"],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ChargeMAX."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except ChargeMaxAuthError:
                errors["base"] = "invalid_auth"
            except ChargeMaxConnectionError:
                errors["base"] = "cannot_connect"
            except NoDevicesError:
                errors["base"] = "no_devices"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Create entry
                await self.async_set_unique_id(user_input[CONF_EMAIL])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class NoDevicesError(Exception):
    """Error to indicate no devices found."""
