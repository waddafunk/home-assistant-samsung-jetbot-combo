"""Select platform for Jet Bot cleaning type via SmartThings entities."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def send_cleaning_type_command_via_smartthings(hass, device_id, cleaning_type):
    """Send a cleaning type command via SmartThings entities."""
    try:
        # Find SmartThings select entities for this device
        entity_registry = async_get_entity_registry(hass)
        
        cleaning_type_entities = []
        for entry in entity_registry.entities.values():
            if (entry.platform == "smartthings" and 
                entry.domain == "select" and
                entry.unique_id and device_id in entry.unique_id):
                # Look for cleaning type or mode select entities
                if any(word in entry.entity_id.lower() for word in ["cleaning", "type", "mode"]):
                    cleaning_type_entities.append(entry.entity_id)
        
        if cleaning_type_entities:
            # Use the first available select entity
            select_entity = cleaning_type_entities[0]
            
            # Convert friendly name to raw value that SmartThings expects
            raw_cleaning_type = cleaning_type
            if cleaning_type == "Vacuum Only":
                raw_cleaning_type = "vacuum"
            elif cleaning_type == "Mop Only":
                raw_cleaning_type = "mop"
            elif cleaning_type == "Vacuum & Mop Together":
                raw_cleaning_type = "vacuumAndMopTogether"
            elif cleaning_type == "Vacuum Then Mop":
                raw_cleaning_type = "mopAfterVacuum"
            
            # Try both raw and friendly names
            for option_value in [raw_cleaning_type, cleaning_type]:
                try:
                    await hass.services.async_call(
                        "select", "select_option",
                        {
                            "entity_id": select_entity,
                            "option": option_value
                        }
                    )
                    _LOGGER.debug("Set cleaning type to %s via entity %s", option_value, select_entity)
                    return
                except Exception as e:
                    _LOGGER.debug("Failed to set option %s: %s", option_value, e)
                    continue
            
            raise Exception(f"Could not set any option variant for {cleaning_type}")
        
        else:
            _LOGGER.warning("No cleaning type select entities found for device %s", device_id)
            # List available entities for debugging
            all_entities = [
                entry.entity_id for entry in entity_registry.entities.values()
                if (entry.platform == "smartthings" and 
                    entry.unique_id and device_id in entry.unique_id)
            ]
            _LOGGER.debug("Available SmartThings entities for device %s: %s", device_id, all_entities)
            raise Exception("No cleaning type select entities found")
        
    except Exception as err:
        _LOGGER.error("Failed to send cleaning type command %s to device %s: %s", cleaning_type, device_id, err)
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
        self._attr_name = f"Samsung Jet Bot {device_id} Cleaning Type"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_cleaning_type"
        self._attr_should_poll = False

    @property
    def options(self) -> list[str]:
        """Return the list of available cleaning types with friendly names."""
        # First try to get from SmartThings entities
        entities = self.coordinator.data.get("entities", {})
        for entity_id, entity_data in entities.items():
            if ("cleaning" in entity_id.lower() and "type" in entity_id.lower() and
                entity_data.get("attributes", {}).get("options")):
                # If SmartThings provides options, use those
                raw_options = entity_data["attributes"]["options"]
                return self._convert_options_to_friendly(raw_options)
        
        # Fallback to component structure
        comps = self.coordinator.data.get("components", {})
        cap = comps.get("main", {}).get("samsungce.robotCleanerCleaningType", {})
        
        supported_types = cap.get("supportedCleaningTypes", {})
        if isinstance(supported_types, dict) and "value" in supported_types:
            raw_options = supported_types["value"]
        else:
            # Default options for Combo AI
            raw_options = ["vacuum", "mop", "vacuumAndMopTogether", "mopAfterVacuum"]

        return self._convert_options_to_friendly(raw_options)

    def _convert_options_to_friendly(self, raw_options):
        """Convert raw options to friendly names."""
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
        # First try to get from SmartThings entities
        entities = self.coordinator.data.get("entities", {})
        for entity_id, entity_data in entities.items():
            if "cleaning" in entity_id.lower() and "type" in entity_id.lower():
                raw_value = entity_data.get("state")
                if raw_value:
                    return self._convert_raw_to_friendly(raw_value)
        
        # Fallback to component structure
        comps = self.coordinator.data.get("components", {})
        cap = comps.get("main", {}).get("samsungce.robotCleanerCleaningType", {})

        cleaning_type = cap.get("cleaningType", {})
        if isinstance(cleaning_type, dict) and "value" in cleaning_type:
            raw_value = cleaning_type["value"]
            return self._convert_raw_to_friendly(raw_value)
            
        return None

    def _convert_raw_to_friendly(self, raw_value):
        """Convert raw value to friendly name."""
        friendly_names = {
            "vacuum": "Vacuum Only",
            "mop": "Mop Only",
            "vacuumAndMopTogether": "Vacuum & Mop Together",
            "mopAfterVacuum": "Vacuum Then Mop",
        }
        return friendly_names.get(raw_value, raw_value)

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

        await send_cleaning_type_command_via_smartthings(
            self.hass, self._device_id, raw_option
        )
        await self.coordinator.async_request_refresh()