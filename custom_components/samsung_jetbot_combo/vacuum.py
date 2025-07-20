"""Support for Samsung Jet Bot vacuum via SmartThings with OAuth tokens."""

import logging

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SMARTTHINGS_BASE_URL

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


async def send_command(
    hass,
    smartthings_entry_id: str,
    device_id: str,
    command: str,
    capability: str = "samsungce.robotCleanerOperatingState",
):
    """Send a command to SmartThings using OAuth token (original method restored)."""
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
                {"component": "main", "capability": capability, "command": command}
            ]
        }
        resp = await session.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        await resp.release()
        _LOGGER.debug("Successfully sent command %s to device %s", command, device_id)
        
    except Exception as err:
        _LOGGER.error("Failed to send command %s to device %s: %s", command, device_id, err)
        raise


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Jet Bot vacuum from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    smartthings_entry_id = entry.data["smartthings_entry_id"]
    device_id = entry.data["device_id"]
    
    async_add_entities(
        [
            JetBotVacuum(
                coordinator, smartthings_entry_id, device_id
            )
        ],
        update_before_add=True,
    )


class JetBotVacuum(CoordinatorEntity, StateVacuumEntity):
    """Representation of a Samsung Jet Bot vacuum."""

    def __init__(self, coordinator, smartthings_entry_id: str, device_id: str):
        super().__init__(coordinator)
        self._smartthings_entry_id = smartthings_entry_id
        self._device_id = device_id
        self._attr_name = coordinator.data.get("label", "Samsung Jet Bot")
        self._attr_unique_id = f"{DOMAIN}_{device_id}"
        self._attr_supported_features = SUPPORT_JETBOT

    @property
    def state(self) -> str:
        """Show the raw operating state."""
        comps = self.coordinator.data.get("components", {})
        raw = (
            comps.get("main", {})
            .get("samsungce.robotCleanerOperatingState", {})
            .get("operatingState")
        )
        if isinstance(raw, dict):
            raw = raw.get("value")
        return str(raw).lower() if raw else super().state or ""

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
    def extra_state_attributes(self) -> dict:
        """Expose all sensor values on the Vacuum card."""
        comps = self.coordinator.data.get("components", {}).get("main", {})
        attrs: dict = {}

        # Helper to unwrap dict or raw
        def _val(cap, key):
            raw = comps.get(cap, {}).get(key)
            if isinstance(raw, dict):
                return raw.get("value")
            return raw

        # Battery
        batt = _val("battery", "battery")
        if batt is not None:
            attrs["battery_level"] = batt

        # Operating state
        op = _val("samsungce.robotCleanerOperatingState", "operatingState")
        if op is not None:
            attrs["operating_state"] = op

        # Cleaning mode
        mode = _val("samsungce.robotCleanerCleaningMode", "robotCleanerCleaningMode")
        if mode is not None:
            attrs["cleaning_mode"] = mode

        # Cleaning step
        step = _val("samsungce.robotCleanerOperatingState", "cleaningStep")
        if step is not None:
            attrs["cleaning_step"] = step

        # Dustbin status
        dust = _val("samsungce.robotCleanerDustBag", "status")
        if dust is not None:
            attrs["dustbin_status"] = dust

        # Water spray level
        spray = _val("samsungce.robotCleanerWaterSprayLevel", "waterSprayLevel")
        if spray is not None:
            attrs["water_spray_level"] = spray

        # Turbo mode
        turbo = _val("samsungce.robotCleanerTurboMode", "robotCleanerTurboMode")
        if turbo is not None:
            attrs["turbo_mode"] = turbo

        # Sound mode
        sound = _val("samsungce.robotCleanerSystemSoundMode", "soundMode")
        if sound is not None:
            attrs["sound_mode"] = sound

        # Map area
        area = _val("samsungce.robotCleanerMapCleaningInfo", "area")
        if area is not None:
            attrs["map_area"] = area

        # Cleaned extent
        extent = _val("samsungce.robotCleanerMapCleaningInfo", "cleanedExtent")
        if extent is not None:
            attrs["cleaned_extent"] = extent

        return attrs

    async def async_start(self):
        _LOGGER.debug("Starting Jet Bot")
        await send_command(self.hass, self._smartthings_entry_id, self._device_id, "start")
        await self.coordinator.async_request_refresh()

    async def async_stop(self, **kwargs):
        _LOGGER.debug("Stopping Jet Bot")
        await send_command(self.hass, self._smartthings_entry_id, self._device_id, "stop")
        await self.coordinator.async_request_refresh()

    async def async_pause(self):
        _LOGGER.debug("Pausing Jet Bot")
        await send_command(self.hass, self._smartthings_entry_id, self._device_id, "pause")
        await self.coordinator.async_request_refresh()

    async def async_return_to_base(self, **kwargs):
        _LOGGER.debug("Returning Jet Bot to dock")
        await send_command(
            self.hass, self._smartthings_entry_id, self._device_id, "returnToHome"
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        await self.async_start()

    async def async_turn_off(self, **kwargs):
        await self.async_stop()