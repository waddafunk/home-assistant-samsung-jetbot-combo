"""Application credentials platform for Samsung Jet Bot integration."""

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# SmartThings OAuth 2.0 endpoints
AUTHORIZATION_SERVER = AuthorizationServer(
    authorize_url="https://account.smartthings.com/oauth/authorize",
    token_url="https://account.smartthings.com/oauth/token",
)


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential
) -> AuthorizationServer:
    """Return auth implementation for domain."""
    return AUTHORIZATION_SERVER


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    return {
        "oauth_url": "https://developer.smartthings.com",
        "more_info_url": "https://github.com/waddafunk/home-assistant-samsung-jetbot-combo",
    }
