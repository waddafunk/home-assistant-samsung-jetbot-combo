"""Initialize the Samsung Jet Bot integration leveraging official SmartThings."""

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .sensor import JetBotDataUpdateCoordinator

PLATFORMS = ["sensor", "vacuum", "select"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Samsung Jet Bot from a config entry."""
    
    # Get the SmartThings integration entry
    smartthings_entry_id = entry.data["smartthings_entry_id"]
    
    # Verify SmartThings integration is loaded
    if "smartthings" not in hass.data:
        raise ConfigEntryNotReady("SmartThings integration not loaded")
    
    if smartthings_entry_id not in hass.data["smartthings"]:
        raise ConfigEntryNotReady(f"SmartThings entry {smartthings_entry_id} not found")
    
    # Get SmartThings API access
    smartthings_data = hass.data["smartthings"][smartthings_entry_id]
    api = smartthings_data["api"]
    device_id = entry.data["device_id"]
    
    # Verify device exists
    try:
        device = await api.device(device_id)
        if not device:
            _LOGGER.error("Device %s not found in SmartThings", device_id)
            return False
    except Exception as err:
        _LOGGER.error("Error accessing device %s: %s", device_id, err)
        raise ConfigEntryNotReady(f"Cannot access device {device_id}") from err

    # Initialize coordinator
    coordinator = JetBotDataUpdateCoordinator(hass, api, device_id)
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "device": device
    }

    # Forward setup
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok