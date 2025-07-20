"""Sensor platform for Samsung Jet Bot with OAuth 2.0 support."""

import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, SMARTTHINGS_BASE_URL

_LOGGER = logging.getLogger(__name__)


class SmartThingsDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch SmartThings device data with OAuth token refresh."""

    def __init__(self, hass, access_token: str, device_id: str):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}",
            update_interval=timedelta(seconds=30),
        )
        self._access_token = access_token
        self._device_id = device_id
        self.oauth_session = None  # Will be set by __init__.py if using OAuth

    async def _get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        try:
            await self.oauth_session.async_ensure_token_valid()
            return self.oauth_session.token["access_token"]
        except Exception as err:
            _LOGGER.error("Failed to refresh OAuth token: %s", err)
            raise ConfigEntryAuthFailed("Token refresh failed") from err

    async def _async_update_data(self):
        """Fetch latest status and device detail from SmartThings."""
        try:
            access_token = await self._get_access_token()
            session = async_get_clientsession(self.hass)
            headers = {"Authorization": f"Bearer {access_token}"}

            # 1) Get device status (all components/attributes)
            status_url = f"{SMARTTHINGS_BASE_URL}/{self._device_id}/status"
            resp = await session.get(status_url, headers=headers)
            
            if resp.status in (401, 403):
                await resp.release()
                raise ConfigEntryAuthFailed("Authentication failed")
            elif resp.status != 200:
                await resp.release()
                raise UpdateFailed(f"Error fetching status: {resp.status}")
                
            status_json = await resp.json()
            await resp.release()

            # 2) Get device details (for the label)
            detail_url = f"{SMARTTHINGS_BASE_URL}/{self._device_id}"
            resp = await session.get(detail_url, headers=headers)
            
            if resp.status in (401, 403):
                await resp.release()
                raise ConfigEntryAuthFailed("Authentication failed")
            elif resp.status != 200:
                await resp.release()
                raise UpdateFailed(f"Error fetching details: {resp.status}")
                
            detail_json = await resp.json()
            await resp.release()

            return {
                "components": status_json.get("components", {}),
                "label": detail_json.get("label"),
            }
            
        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            _LOGGER.error("Error updating data: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensors for Samsung Jet Bot."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device_id = entry.data["device_id"]

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
            key="mode",
            name="Cleaning Mode",
            capability="samsungce.robotCleanerCleaningMode",
            value_key="robotCleanerCleaningMode",
            component="main",
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
            key="step",
            name="Cleaning Step",
            capability="samsungce.robotCleanerOperatingState",
            value_key="cleaningStep",
            component="main",
        ),
        JetBotSensor(
            coordinator,
            device_id,
            key="dustbin",
            name="Dustbin Status",
            capability="samsungce.robotCleanerDustBag",
            value_key="status",
            component="station",
        ),
        JetBotSensor(
            coordinator,
            device_id,
            key="spray",
            name="Water Spray Level",
            capability="samsungce.robotCleanerWaterSprayLevel",
            value_key="waterSprayLevel",
            component="main",
        ),
        JetBotSensor(
            coordinator,
            device_id,
            key="turbo",
            name="Turbo Mode",
            capability="samsungce.robotCleanerTurboMode",
            value_key="robotCleanerTurboMode",
            component="main",
        ),
        JetBotSensor(
            coordinator,
            device_id,
            key="sound",
            name="Sound Mode",
            capability="samsungce.robotCleanerSystemSoundMode",
            value_key="soundMode",
            component="main",
        ),
        JetBotSensor(
            coordinator,
            device_id,
            key="map_area",
            name="Map Area",
            capability="samsungce.robotCleanerMapCleaningInfo",
            value_key="area",
            component="main",
        ),
        JetBotSensor(
            coordinator,
            device_id,
            key="extent",
            name="Cleaned Extent",
            capability="samsungce.robotCleanerMapCleaningInfo",
            value_key="cleanedExtent",
            component="main",
        ),
    ]

    async_add_entities(sensors, update_before_add=True)


class JetBotSensor(CoordinatorEntity, SensorEntity):
    """Generic sensor for Samsung Jet Bot attributes."""

    def __init__(
        self,
        coordinator: SmartThingsDataUpdateCoordinator,
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
        comps = self.coordinator.data.get("components", {})
        cap = comps.get(self._component, {}).get(self._capability, {})
        raw = cap.get(self._value_key)
        if isinstance(raw, dict) and "value" in raw:
            return raw["value"]
        return raw