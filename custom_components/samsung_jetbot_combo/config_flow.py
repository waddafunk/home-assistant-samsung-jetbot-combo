"""Config flow for Samsung Jet Bot with simplified setup."""

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, SMARTTHINGS_BASE_URL

_LOGGER = logging.getLogger(__name__)


class SamsungJetBotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Samsung Jet Bot."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle user step."""
        errors = {}
        
        if user_input is not None:
            device_id = user_input["device_id"]
            
            # Check if SmartThings integration exists and is loaded
            smartthings_entries = [
                entry for entry in self.hass.config_entries.async_entries("smartthings")
                if entry.state == config_entries.ConfigEntryState.LOADED
            ]
            
            if not smartthings_entries:
                errors["base"] = "missing_smartthings"
            else:
                # Store reference to SmartThings entry
                smartthings_entry_id = smartthings_entries[0].entry_id
                
                return self.async_create_entry(
                    title=f"Samsung Jet Bot ({device_id})",
                    data={
                        "device_id": device_id,
                        "smartthings_entry_id": smartthings_entry_id,
                    }
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("device_id"): str,
            }),
            errors=errors,
            description_placeholders={
                "smartthings_setup_url": "https://my.home-assistant.io/redirect/config_flow_start/?domain=smartthings"
            }
        )