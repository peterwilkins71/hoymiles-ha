from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HoymilesCloud
from .const import CONF_STATION_ID
from .coordinator import LiveCoordinator, TotalsCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


@dataclass
class HoymilesData:
    live: LiveCoordinator
    totals: TotalsCoordinator


type HoymilesConfigEntry = ConfigEntry[HoymilesData]


async def async_setup_entry(hass: HomeAssistant, entry: HoymilesConfigEntry) -> bool:
    api = HoymilesCloud(async_get_clientsession(hass), entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    sid = int(entry.data[CONF_STATION_ID])
    live = LiveCoordinator(hass, entry, api, sid)
    totals = TotalsCoordinator(hass, entry, api, sid)
    await totals.async_config_entry_first_refresh()
    await live.async_config_entry_first_refresh()
    entry.runtime_data = HoymilesData(live=live, totals=totals)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HoymilesConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
