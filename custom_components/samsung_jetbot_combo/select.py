"""Select platform for Jet Bot cleaning type using OAuth tokens (original method restored)."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SMARTTHINGS_BASE_URL

_LOGGER = logging.getLogger(__name__)


async def get_smartthings_access_token(hass, smartthings_entry_id):
    """Get the access token from the SmartThings integration."""
    try:
        # Get the SmartThings integration entry
        smartthings_entry = hass.config_entries.async_get_entry(smartthings_entry_id)
        if not smartthings_entry:
            raise Exception("SmartThings entry not found")
        
        # Get the OAuth session from the SmartThings integration
        if "smartthings" in hass.data and smartthings_entry_id in hass.data["smartthings"]:
            smartthings_data = hass.data["smartthings"][smartthings_entry_id]
            
            # Try different ways to get the token depending on the integration structure
            if hasattr(smartthings_data, 'api') and hasattr(smartthings_data.api, '_token'):
                return smartthings_data.api._token
            elif 'token' in smartthings_data:
                return smartthings_data['token']
            elif hasattr(smartthings_data, 'token'):
                return smartthings_data.token
        
        # Fallback: try to get token from the entry data
        if 'token' in smartthings_entry.data:
            return smartthings_entry.data['token']['access_token']
            
        raise Exception("Could not extract access token from SmartThings integration")
        
    except Exception as err:
        _LOGGER.error("Failed to get SmartThings access token: %s", err)
        raise


async def send_cleaning_type_command(
    hass,
    smartthings_entry_id: str,
    device_id: str,
    cleaning_type: str,
):
    """Send a cleaning type command to SmartThings using OAuth token (original method restored)."""
    try:
        access_token = await get_smartthings_access_token(hass, smartthings_entry_id)
        session = async_get_clientsession(hass)
        url = f"{SMARTTHINGS_BASE_URL}/{device_id}/commands"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.smartthings+json;v=1",
        }
        payload = {
            "commands": [
                {
                    "component": "main",
                    "capability": "samsungce.robotCleanerCleaningType",
                    "command": "setCleaningType",
                    "arguments": [cleaning_type],
                }
            ]
        }
        resp = await session.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        await resp.release()
        _LOGGER.debug("Successfully sent cleaning type command %s to device %s", cleaning_type, device_id)
        
    except Exception as err:
        _LOGGER.error("Failed to send cleaning type command %s to device %s: %s", cleaning_type, device_id, err)
        raise


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up select platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    smartthings_entry_id = entry.data["smartthings_entry_id"]
    device_id = entry.data["device_id"]

    async_add_entities(
        [JetBotCleaningTypeSelect(coordinator, smartthings_entry_id, device_id)],
        update_before_add=True,
    )


class JetBotCleaningTypeSelect(CoordinatorEntity, SelectEntity):
    """Cleaning type select for Jet Bot Combo AI."""

    def __init__(self, coordinator, smartthings_entry_id, device_id):
        super().__init__(coordinator)
        self._smartthings_entry_id = smartthings_entry_id
        self._device_id = device_id
        self._attr_name = (
            f"{coordinator.data.get('label','Jet Bot Vacuum')} Cleaning Type"
        )
        self._attr_unique_id = f"{DOMAIN}_{device_id}_cleaning_type"
        self._attr_should_poll = False

    @property
    def options(self) -> list[str]:
        """Return the list of available cleaning types with friendly names."""
        comps = self.coordinator.data.get("components", {})
        cap = comps.get("main", {}).get("samsungce.robotCleanerCleaningType", {})

        # Get supported cleaning types from the capability
        supported_types = cap.get("supportedCleaningTypes", {})
        if isinstance(supported_types, dict) and "value" in supported_types:
            raw_options = supported_types["value"]
        else:
            # Fallback to common Combo AI cleaning types
            raw_options = ["vacuum", "mop", "vacuumAndMopTogether", "mopAfterVacuum"]

        # Create user-friendly names
        friendly_names = {
            "vacuum": "Vacuum Only",
            "mop": "Mop Only",
            "vacuumAndMopTogether": "Vacuum & Mop Together",
            "mopAfterVacuum": "Vacuum Then Mop",
        }

        return [friendly_names.get(option, option) for option in raw_options]

    @property
    def current_option(self) -> str | None:
        """Return the current cleaning type with friendly name."""
        comps = self.coordinator.data.get("components", {})
        cap = comps.get("main", {}).get("samsungce.robotCleanerCleaningType", {})

        # Get current cleaning type from the capability
        cleaning_type = cap.get("cleaningType", {})
        if isinstance(cleaning_type, dict) and "value" in cleaning_type:
            raw_value = cleaning_type["value"]

            # Convert to friendly name
            friendly_names = {
                "vacuum": "Vacuum Only",
                "mop": "Mop Only",
                "vacuumAndMopTogether": "Vacuum & Mop Together",
                "mopAfterVacuum": "Vacuum Then Mop",
            }

            return friendly_names.get(raw_value, raw_value)
        return None

    @property
    def icon(self) -> str:
        """Return the icon for the select entity."""
        current = self.current_option
        if current == "Vacuum Only":
            return "mdi:robot-vacuum"
        if current == "Mop Only":
            return "mdi:spray-bottle"
        if current in ["Vacuum & Mop Together", "Vacuum Then Mop"]:
            return "mdi:robot-vacuum-variant"
        return "mdi:robot-vacuum"

    def _friendly_to_raw(self, friendly_name: str) -> str:
        """Convert friendly name back to raw API value."""
        name_mapping = {
            "Vacuum Only": "vacuum",
            "Mop Only": "mop",
            "Vacuum & Mop Together": "vacuumAndMopTogether",
            "Vacuum Then Mop": "mopAfterVacuum",
        }
        return name_mapping.get(friendly_name, friendly_name)

    async def async_select_option(self, option: str) -> None:
        """Set the cleaning type."""
        _LOGGER.debug("Setting cleaning type to %s", option)

        # Convert friendly name back to raw API value
        raw_option = self._friendly_to_raw(option)

        await send_cleaning_type_command(
            self.hass, self._smartthings_entry_id, self._device_id, raw_option
        )
        await self.coordinator.async_request_refresh()