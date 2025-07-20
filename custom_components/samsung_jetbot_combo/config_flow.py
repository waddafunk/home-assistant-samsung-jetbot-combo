"""Config flow for Samsung Jet Bot leveraging official SmartThings integration."""

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.smartthings.config_flow import SmartThingsFlowHandler
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, SMARTTHINGS_BASE_URL

_LOGGER = logging.getLogger(__name__)


class SamsungJetBotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow that leverages the official SmartThings OAuth integration."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._smartthings_entry = None
        self._vacuum_devices = []

    async def async_step_user(self, user_input=None):
        """Handle user step - check for SmartThings integration."""
        # Check if SmartThings integration is already configured
        smartthings_entries = [
            entry for entry in self.hass.config_entries.async_entries("smartthings")
            if entry.state == config_entries.ConfigEntryState.LOADED
        ]
        
        if not smartthings_entries:
            return self.async_abort(
                reason="missing_smartthings",
                description_placeholders={
                    "smartthings_url": "https://my.home-assistant.io/redirect/config_flow_start/?domain=smartthings"
                }
            )
        
        # Use the first available SmartThings entry
        self._smartthings_entry = smartthings_entries[0]
        
        # Get the SmartThings API manager from the integration
        try:
            smartthings_data = self.hass.data["smartthings"][self._smartthings_entry.entry_id]
            api = smartthings_data["api"]
            
            # Get all devices
            devices = await api.devices()
            
            # Filter for vacuum devices
            vacuum_devices = []
            for device in devices:
                # Check if device has robot cleaner capabilities
                if any(
                    "robotCleanerOperatingState" in cap.name.lower()
                    for cap in device.capabilities
                ):
                    vacuum_devices.append({
                        "device_id": device.device_id,
                        "label": device.label or device.device_id,
                        "location": device.location_id
                    })
            
            if not vacuum_devices:
                return self.async_abort(reason="no_vacuum_devices")
            
            if len(vacuum_devices) == 1:
                # Auto-select single device
                device = vacuum_devices[0]
                return self.async_create_entry(
                    title=f"Samsung Jet Bot ({device['label']})",
                    data={
                        "device_id": device["device_id"],
                        "device_label": device["label"],
                        "smartthings_entry_id": self._smartthings_entry.entry_id
                    }
                )
            else:
                # Multiple devices - let user choose
                self._vacuum_devices = vacuum_devices
                return await self.async_step_device_selection()
                
        except Exception as err:
            _LOGGER.error("Error accessing SmartThings API: %s", err)
            return self.async_abort(reason="cannot_connect")

    async def async_step_device_selection(self, user_input=None):
        """Handle device selection when multiple vacuum devices are found."""
        errors = {}
        
        if user_input is not None:
            device_id = user_input["device"]
            selected_device = next(
                (dev for dev in self._vacuum_devices if dev["device_id"] == device_id),
                None
            )
            
            if selected_device:
                return self.async_create_entry(
                    title=f"Samsung Jet Bot ({selected_device['label']})",
                    data={
                        "device_id": selected_device["device_id"],
                        "device_label": selected_device["label"],
                        "smartthings_entry_id": self._smartthings_entry.entry_id
                    }
                )
            else:
                errors["device"] = "invalid_device"
        
        device_options = {
            device["device_id"]: f"{device['label']} ({device['device_id']})"
            for device in self._vacuum_devices
        }
        
        return self.async_show_form(
            step_id="device_selection",
            data_schema=vol.Schema({
                vol.Required("device"): vol.In(device_options)
            }),
            errors=errors,
        )