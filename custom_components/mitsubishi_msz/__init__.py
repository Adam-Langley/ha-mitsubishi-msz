"""Direct local control of a Mitsubishi indoor unit via a MAC-559IF-E adapter."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MitsubishiLocalApi
from .const import CONF_SCAN_INTERVAL_SECONDS, DEFAULT_SCAN_INTERVAL
from .coordinator import MszCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one indoor unit."""
    api = MitsubishiLocalApi(entry.data[CONF_HOST], async_get_clientsession(hass))
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL_SECONDS, DEFAULT_SCAN_INTERVAL
    )
    coordinator = MszCoordinator(hass, entry, api, scan_interval)

    await coordinator.async_load_unit_info()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Tear the unit down again."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when the poll interval is changed in the options."""
    await hass.config_entries.async_reload(entry.entry_id)
