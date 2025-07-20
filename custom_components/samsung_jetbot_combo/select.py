"""Select platform for Jet Bot cleaning type (vacuum/mop/both) with OAuth 2.0."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SMARTTHINGS_BASE_URL

_LOGGER = logging.getLogger(__name__)


async def send_cleaning_type_command(
    hass,
    coordinator,
    device_id: str,
    cleaning_type: str,
):
    """Send a cleaning type command to SmartThings with OAuth token refresh."""
    try:
        access_token = await coordinator._get_access_token()
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
        
        if resp.status in (401, 403):
            await resp.release()
            raise ConfigEntryAuthFailed("Authentication failed")
            
        resp.raise_for_status()
        await resp.release()
        
    except ConfigEntryAuthFailed:
        raise
    except Exception as err:
        _LOGGER.error("Failed to send cleaning type command %s: %s", cleaning_type, err)
        raise


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up select platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device_id = entry.data["device_id"]

    async_add_entities(
        [JetBotCleaningTypeSelect(coordinator, device_id)],
        update_before_add=True,
    )


class JetBotCleaningTypeSelect(CoordinatorEntity, SelectEntity):
    """Cleaning type select for Jet Bot Combo AI."""

    def __init__(self, coordinator, device_id):
        super().__init__(coordinator)
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
            self.hass, self.coordinator, self._device_id, raw_option
        )
        await self.coordinator.async_request_refresh()