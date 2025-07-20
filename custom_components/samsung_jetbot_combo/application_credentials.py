"""Application credentials platform for Samsung Jet Bot integration."""

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server for SmartThings OAuth."""
    return AuthorizationServer(
        authorize_url="https://account.smartthings.com/oauth/authorize",
        token_url="https://account.smartthings.com/oauth/token",
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    return {
        "oauth_url": "https://developer.smartthings.com",
        "more_info_url": "https://github.com/waddafunk/home-assistant-samsung-jetbot-combo",
    }