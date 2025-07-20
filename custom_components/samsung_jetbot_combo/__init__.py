"""Initialize the Samsung Jet Bot integration leveraging SmartThings entities."""

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
    
    device_id = entry.data["device_id"]
    smartthings_entry_id = entry.data["smartthings_entry_id"]
    
    # Verify SmartThings integration is loaded
    smartthings_entry = hass.config_entries.async_get_entry(smartthings_entry_id)
    if not smartthings_entry or smartthings_entry.state != ConfigEntry.ConfigEntryState.LOADED:
        raise ConfigEntryNotReady("SmartThings integration not loaded")

    # Initialize coordinator that will work with SmartThings entities
    coordinator = JetBotDataUpdateCoordinator(hass, device_id, smartthings_entry_id)
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "device_id": device_id,
        "smartthings_entry_id": smartthings_entry_id
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