"""Config flow for Samsung Jet Bot."""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, SMARTTHINGS_BASE_URL

_LOGGER = logging.getLogger(__name__)


class SamsungJetBotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Samsung Jet Bot."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Initial step."""
        errors = {}
        if user_input:
            token = user_input["access_token"]
            device_id = user_input["device_id"]
            session = async_get_clientsession(self.hass)
            try:
                resp = await session.get(
                    f"{SMARTTHINGS_BASE_URL}/{device_id}/status",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status == 200:
                    await resp.release()
                    return self.async_create_entry(
                        title=f"Samsung Jet Bot {device_id}", data=user_input
                    )
                errors["base"] = (
                    "invalid_auth" if resp.status in (401, 403) else "invalid_device"
                )
                await resp.release()
            except Exception:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("access_token"): str,
                    vol.Required("device_id"): str,
                }
            ),
            errors=errors,
        )
