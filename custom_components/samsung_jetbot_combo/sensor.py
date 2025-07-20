"""Sensor platform for Samsung Jet Bot leveraging SmartThings entities."""

import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class JetBotDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch Samsung Jet Bot data from SmartThings entities."""

    def __init__(self, hass, device_id: str, smartthings_entry_id: str):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}",
            update_interval=timedelta(seconds=30),
        )
        self._device_id = device_id
        self._smartthings_entry_id = smartthings_entry_id

    async def _async_update_data(self):
        """Fetch latest status from SmartThings entities."""
        try:
            # Get entity registry to find SmartThings entities for this device
            entity_registry = async_get_entity_registry(self.hass)
            
            # Find all SmartThings entities for this device
            smartthings_entities = [
                entry for entry in entity_registry.entities.values()
                if entry.config_entry_id == self._smartthings_entry_id
                and entry.unique_id and self._device_id in entry.unique_id
            ]
            
            if not smartthings_entities:
                raise UpdateFailed(f"No SmartThings entities found for device {self._device_id}")
            
            # Collect current state from all related entities
            device_data = {
                "components": {"main": {}},
                "label": f"Samsung Jet Bot {self._device_id}",
                "entities": {}
            }
            
            for entity_entry in smartthings_entities:
                entity_id = entity_entry.entity_id
                state = self.hass.states.get(entity_id)
                
                if state:
                    # Store entity data for easy access
                    device_data["entities"][entity_id] = {
                        "state": state.state,
                        "attributes": state.attributes
                    }
                    
                    # Try to map to SmartThings capability structure
                    # This is a simplified mapping - extend as needed
                    if "battery" in entity_id:
                        device_data["components"]["main"]["battery"] = {
                            "battery": {"value": state.state}
                        }
                    elif "operating" in entity_id or "state" in entity_id:
                        device_data["components"]["main"]["samsungce.robotCleanerOperatingState"] = {
                            "operatingState": {"value": state.state}
                        }
                    elif "cleaning" in entity_id and "mode" in entity_id:
                        device_data["components"]["main"]["samsungce.robotCleanerCleaningMode"] = {
                            "robotCleanerCleaningMode": {"value": state.state}
                        }
            
            return device_data
            
        except Exception as err:
            _LOGGER.error("Error updating data for device %s: %s", self._device_id, err)
            raise UpdateFailed(f"Error communicating with SmartThings entities: {err}") from err


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensors for Samsung Jet Bot."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device_id = entry.data["device_id"]

    # Create enhanced sensors that work with the coordinator
    sensors = [
        JetBotSensor(
            coordinator,
            device_id,
            key="battery",
            name="Jet Bot Battery",
            capability="battery",
            value_key="battery",
            component="main",
            unit_of_measurement="%",
            icon="mdi:battery",
        ),
        JetBotSensor(
            coordinator,
            device_id,
            key="state",
            name="Operating State",
            capability="samsungce.robotCleanerOperatingState",
            value_key="operatingState",
            component="main",
        ),
        JetBotSensor(
            coordinator,
            device_id,
            key="mode",
            name="Cleaning Mode",
            capability="samsungce.robotCleanerCleaningMode",
            value_key="robotCleanerCleaningMode",
            component="main",
        ),
    ]

    async_add_entities(sensors, update_before_add=True)


class JetBotSensor(CoordinatorEntity, SensorEntity):
    """Generic sensor for Samsung Jet Bot attributes."""

    def __init__(
        self,
        coordinator: JetBotDataUpdateCoordinator,
        device_id: str,
        key: str,
        name: str,
        capability: str,
        value_key: str,
        component: str,
        unit_of_measurement: str | None = None,
        icon: str | None = None,
    ):
        super().__init__(coordinator)
        self._device_id = device_id
        self._key = key
        self._capability = capability
        self._value_key = value_key
        self._component = component

        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{key}"

        if unit_of_measurement:
            self._attr_native_unit_of_measurement = unit_of_measurement
        if icon:
            self._attr_icon = icon

    @property
    def native_value(self):
        """Extract the latest value from coordinator data."""
        # Try to get from structured components first
        comps = self.coordinator.data.get("components", {})
        cap = comps.get(self._component, {}).get(self._capability, {})
        raw = cap.get(self._value_key)
        if isinstance(raw, dict) and "value" in raw:
            return raw["value"]
        elif raw is not None:
            return raw
            
        # Fallback: look for matching entity data
        entities = self.coordinator.data.get("entities", {})
        for entity_id, entity_data in entities.items():
            if self._key in entity_id:
                return entity_data["state"]
                
        return None