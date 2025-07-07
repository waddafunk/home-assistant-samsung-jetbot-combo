"""Select platform for Jet Bot cleaning mode."""
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .vacuum import send_command

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up select platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    access_token = entry.data["access_token"]
    device_id = entry.data["device_id"]

    async_add_entities([JetBotModeSelect(coordinator, access_token, device_id)], update_before_add=True)

class JetBotModeSelect(CoordinatorEntity, SelectEntity):
    """Cleaning mode select for Jet Bot."""

    def __init__(self, coordinator, access_token, device_id):
        super().__init__(coordinator)
        self._access_token = access_token
        self._device_id = device_id
        self._attr_name = f"{coordinator.data.get('label','Jet Bot Vacuum')} Mode"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_mode"
        self._attr_should_poll = False

    @property
    def options(self) -> list[str]:
        comps = self.coordinator.data.get("components",{})
        cap = comps.get("main",{}).get("samsungce.robotCleanerCleaningMode",{})
        vals = cap.get("supportedValues") or []
        if vals and isinstance(vals[0],dict):
            return [v.get("value") for v in vals if "value" in v]
        return vals

    @property
    def current_option(self) -> str | None:
        comps = self.coordinator.data.get("components",{})
        cap = comps.get("main",{}).get("samsungce.robotCleanerCleaningMode",{})
        raw = cap.get("robotCleanerCleaningMode")
        if isinstance(raw,dict) and "value" in raw:
            return raw["value"]
        return raw

    async def async_select_option(self, option: str) -> None:
        _LOGGER.debug("Setting mode to %s", option)
        await send_command(self.hass, self._access_token, self._device_id, option, capability="samsungce.robotCleanerCleaningMode")
        await self.coordinator.async_request_refresh()
