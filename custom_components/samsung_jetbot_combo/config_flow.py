"""Config flow for Samsung Jet Bot with OAuth 2.0 support only."""

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, SMARTTHINGS_BASE_URL

_LOGGER = logging.getLogger(__name__)


class SamsungJetBotOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Samsung Jet Bot OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": "r:devices:* r:locations:* x:devices:*"
        }

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> config_entries.ConfigFlowResult:
        """Create an entry for Samsung Jet Bot."""
        # Use the token to fetch available devices
        session = async_get_clientsession(self.hass)
        headers = {"Authorization": f"Bearer {data['token']['access_token']}"}
        
        try:
            # Get devices to let user select which one to use
            resp = await session.get(f"{SMARTTHINGS_BASE_URL}", headers=headers)
            resp.raise_for_status()
            devices_data = await resp.json()
            await resp.release()
            
            devices = devices_data.get("items", [])
            
            # Filter for robot vacuum devices (devices with robotCleanerOperatingState capability)
            vacuum_devices = []
            for device in devices:
                if any(
                    "robotCleanerOperatingState" in str(cap).lower()
                    for comp in device.get("components", [])
                    for cap in comp.get("capabilities", [])
                ):
                    vacuum_devices.append({
                        "device_id": device["deviceId"],
                        "label": device.get("label", device["deviceId"]),
                        "location": device.get("locationId", "Unknown")
                    })
            
            if not vacuum_devices:
                return self.async_abort(reason="no_vacuum_devices")
            
            if len(vacuum_devices) == 1:
                # If only one vacuum device, use it automatically
                device = vacuum_devices[0]
                data["device_id"] = device["device_id"]
                data["device_label"] = device["label"]
                return self.async_create_entry(
                    title=f"Samsung Jet Bot ({device['label']})", 
                    data=data
                )
            else:
                # Store devices for selection step
                self._vacuum_devices = vacuum_devices
                self._oauth_data = data
                return await self.async_step_device_selection()
                
        except Exception as err:
            _LOGGER.error("Error fetching devices: %s", err)
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
                self._oauth_data["device_id"] = selected_device["device_id"]
                self._oauth_data["device_label"] = selected_device["label"]
                return self.async_create_entry(
                    title=f"Samsung Jet Bot ({selected_device['label']})",
                    data=self._oauth_data
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

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> config_entries.ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={
                    "account": self.reauth_entry.data.get("device_label", "Samsung Jet Bot")
                },
            )
        return await self.async_step_user()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return await self.async_step_pick_implementation(user_input)