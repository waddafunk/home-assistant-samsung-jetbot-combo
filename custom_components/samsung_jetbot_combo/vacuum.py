"""Support for Samsung Jet Bot vacuum via SmartThings entities."""

import logging

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORT_JETBOT = (
    VacuumEntityFeature.STATE
    | VacuumEntityFeature.START
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.TURN_ON
    | VacuumEntityFeature.TURN_OFF
)


async def send_command_via_smartthings(hass, device_id, command, capability="samsungce.robotCleanerOperatingState"):
    """Send a command via SmartThings entities."""
    try:
        # Find SmartThings entities for this device
        entity_registry = async_get_entity_registry(hass)
        
        # Get all SmartThings entities for this device
        device_entities = []
        for entry in entity_registry.entities.values():
            if (entry.platform == "smartthings" and 
                entry.unique_id and device_id in entry.unique_id):
                device_entities.append({
                    "entity_id": entry.entity_id,
                    "domain": entry.domain,
                    "unique_id": entry.unique_id
                })
        
        _LOGGER.debug("Found %d SmartThings entities for device %s", len(device_entities), device_id)
        
        # Try to execute the command through appropriate entities
        if command == "start":
            # Look for switch entities that might start the vacuum
            for entity in device_entities:
                entity_id = entity["entity_id"]
                if entity["domain"] == "switch":
                    if any(word in entity_id.lower() for word in ["vacuum", "clean", "start", "power"]):
                        await hass.services.async_call("switch", "turn_on", {"entity_id": entity_id})
                        _LOGGER.debug("Started vacuum via switch entity: %s", entity_id)
                        return
                elif entity["domain"] == "button":
                    if any(word in entity_id.lower() for word in ["start", "clean", "play"]):
                        await hass.services.async_call("button", "press", {"entity_id": entity_id})
                        _LOGGER.debug("Started vacuum via button entity: %s", entity_id)
                        return
        
        elif command == "stop":
            for entity in device_entities:
                entity_id = entity["entity_id"]
                if entity["domain"] == "switch":
                    if any(word in entity_id.lower() for word in ["vacuum", "clean", "power"]):
                        await hass.services.async_call("switch", "turn_off", {"entity_id": entity_id})
                        _LOGGER.debug("Stopped vacuum via switch entity: %s", entity_id)
                        return
                elif entity["domain"] == "button":
                    if any(word in entity_id.lower() for word in ["stop", "pause"]):
                        await hass.services.async_call("button", "press", {"entity_id": entity_id})
                        _LOGGER.debug("Stopped vacuum via button entity: %s", entity_id)
                        return
        
        elif command == "pause":
            for entity in device_entities:
                entity_id = entity["entity_id"]
                if entity["domain"] == "button":
                    if "pause" in entity_id.lower():
                        await hass.services.async_call("button", "press", {"entity_id": entity_id})
                        _LOGGER.debug("Paused vacuum via button entity: %s", entity_id)
                        return
        
        elif command == "returnToHome":
            for entity in device_entities:
                entity_id = entity["entity_id"]
                if entity["domain"] == "button":
                    if any(word in entity_id.lower() for word in ["home", "dock", "return"]):
                        await hass.services.async_call("button", "press", {"entity_id": entity_id})
                        _LOGGER.debug("Returned vacuum home via button entity: %s", entity_id)
                        return
        
        # If no specific entity found, log available entities for debugging
        _LOGGER.warning("No suitable entity found for command %s. Available entities: %s", 
                       command, [e["entity_id"] for e in device_entities])
        
    except Exception as err:
        _LOGGER.error("Failed to send command %s to device %s: %s", command, device_id, err)
        raise


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Jet Bot vacuum from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device_id = entry.data["device_id"]
    
    async_add_entities(
        [JetBotVacuum(coordinator, device_id)],
        update_before_add=True,
    )


class JetBotVacuum(CoordinatorEntity, StateVacuumEntity):
    """Representation of a Samsung Jet Bot vacuum."""

    def __init__(self, coordinator, device_id: str):
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_name = f"Samsung Jet Bot {device_id}"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_vacuum"
        self._attr_supported_features = SUPPORT_JETBOT

    @property
    def state(self) -> str:
        """Show the raw operating state."""
        # Get state from coordinator data or SmartThings entities
        entities = self.coordinator.data.get("entities", {})
        
        # Look for operating state in entities
        for entity_id, entity_data in entities.items():
            if ("operating" in entity_id.lower() or 
                "state" in entity_id.lower() or
                "vacuum" in entity_id.lower()):
                state = entity_data.get("state", "").lower()
                if state in ["cleaning", "paused", "docked", "idle", "returning"]:
                    return state
        
        # Fallback to components structure
        comps = self.coordinator.data.get("components", {})
        raw = (
            comps.get("main", {})
            .get("samsungce.robotCleanerOperatingState", {})
            .get("operatingState")
        )
        if isinstance(raw, dict):
            raw = raw.get("value")
        return str(raw).lower() if raw else "unknown"

    @property
    def activity(self) -> VacuumActivity:
        """Map the raw state into VacuumActivity for HA internals."""
        st = self.state
        if st == "cleaning":
            return VacuumActivity.CLEANING
        if st == "paused":
            return VacuumActivity.PAUSED
        if st in ("returning", "return_to_base", "returntohome"):
            return VacuumActivity.RETURNING
        if st == "docked":
            return VacuumActivity.DOCKED
        if st == "idle":
            return VacuumActivity.IDLE
        return VacuumActivity.IDLE

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        # Look for battery in entities
        entities = self.coordinator.data.get("entities", {})
        for entity_id, entity_data in entities.items():
            if "battery" in entity_id.lower():
                try:
                    return int(float(entity_data.get("state", 0)))
                except (ValueError, TypeError):
                    pass
        
        # Fallback to components structure
        comps = self.coordinator.data.get("components", {})
        batt = comps.get("main", {}).get("battery", {}).get("battery")
        if isinstance(batt, dict):
            batt = batt.get("value")
        try:
            return int(float(batt)) if batt is not None else None
        except (ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict:
        """Expose all sensor values on the Vacuum card."""
        attrs = {}
        
        # Get attributes from SmartThings entities
        entities = self.coordinator.data.get("entities", {})
        for entity_id, entity_data in entities.items():
            entity_attrs = entity_data.get("attributes", {})
            state = entity_data.get("state")
            
            # Map common attributes
            if "battery" in entity_id.lower():
                attrs["battery_level"] = state
            elif "operating" in entity_id.lower() or "state" in entity_id.lower():
                attrs["operating_state"] = state
            elif "cleaning" in entity_id.lower() and "mode" in entity_id.lower():
                attrs["cleaning_mode"] = state
            elif "dustbin" in entity_id.lower():
                attrs["dustbin_status"] = state
            elif "spray" in entity_id.lower() or "water" in entity_id.lower():
                attrs["water_spray_level"] = state
            elif "turbo" in entity_id.lower():
                attrs["turbo_mode"] = state
            elif "sound" in entity_id.lower():
                attrs["sound_mode"] = state
        
        # Fallback to original component structure if available
        comps = self.coordinator.data.get("components", {}).get("main", {})
        
        def _val(cap, key):
            raw = comps.get(cap, {}).get(key)
            if isinstance(raw, dict):
                return raw.get("value")
            return raw

        # Add any missing attributes from components
        if "battery_level" not in attrs:
            batt = _val("battery", "battery")
            if batt is not None:
                attrs["battery_level"] = batt

        if "operating_state" not in attrs:
            op = _val("samsungce.robotCleanerOperatingState", "operatingState")
            if op is not None:
                attrs["operating_state"] = op

        return attrs

    async def async_start(self):
        """Start cleaning."""
        _LOGGER.debug("Starting Jet Bot")
        await send_command_via_smartthings(self.hass, self._device_id, "start")
        await self.coordinator.async_request_refresh()

    async def async_stop(self, **kwargs):
        """Stop cleaning."""
        _LOGGER.debug("Stopping Jet Bot")
        await send_command_via_smartthings(self.hass, self._device_id, "stop")
        await self.coordinator.async_request_refresh()

    async def async_pause(self):
        """Pause cleaning."""
        _LOGGER.debug("Pausing Jet Bot")
        await send_command_via_smartthings(self.hass, self._device_id, "pause")
        await self.coordinator.async_request_refresh()

    async def async_return_to_base(self, **kwargs):
        """Return to dock."""
        _LOGGER.debug("Returning Jet Bot to dock")
        await send_command_via_smartthings(self.hass, self._device_id, "returnToHome")
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        """Turn on the vacuum."""
        await self.async_start()

    async def async_turn_off(self, **kwargs):
        """Turn off the vacuum."""
        await self.async_stop()