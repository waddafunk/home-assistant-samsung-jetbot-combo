"""Initialize the Samsung Jet Bot integration with OAuth 2.0 support."""

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .sensor import SmartThingsDataUpdateCoordinator

PLATFORMS = ["sensor", "vacuum", "select"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Samsung Jet Bot from a config entry."""
    
    # OAuth 2.0 flow (required)
    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
        hass, entry
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    
    try:
        await session.async_ensure_token_valid()
    except Exception as err:
        _LOGGER.error("Token refresh failed: %s", err)
        raise ConfigEntryAuthFailed("Token refresh failed") from err
        
    access_token = session.token["access_token"]
    device_id = entry.data["device_id"]

    # Test the connection
    session_client = async_get_clientsession(hass)
    try:
        resp = await session_client.get(
            f"https://api.smartthings.com/v1/devices/{device_id}/status",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status in (401, 403):
            await resp.release()
            raise ConfigEntryAuthFailed("Authentication failed")
        elif resp.status != 200:
            await resp.release()
            return False
        await resp.release()
    except ConfigEntryAuthFailed:
        raise
    except Exception as err:
        _LOGGER.error("Connection test failed: %s", err)
        return False

    # Initialize and refresh coordinator
    coordinator = SmartThingsDataUpdateCoordinator(hass, access_token, device_id)
    
    # Pass the OAuth session to coordinator for token refresh
    coordinator.oauth_session = session
        
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    # Forward setup
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok