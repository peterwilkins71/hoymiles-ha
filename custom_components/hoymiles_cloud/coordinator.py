from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HoymilesAuthError, HoymilesCloud, HoymilesError
from .const import DOMAIN, LIVE_INTERVAL_S, TOTALS_INTERVAL_S

_LOGGER = logging.getLogger(__name__)


class _Base(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: HoymilesCloud,
                 sid: int, name: str, seconds: int) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} {name}",
                         update_interval=timedelta(seconds=seconds))
        self.api = api
        self.sid = sid

    async def _fetch(self) -> dict[str, Any]:
        raise NotImplementedError

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self._fetch()
        except HoymilesAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (HoymilesError, aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(str(err)) from err


class LiveCoordinator(_Base):
    def __init__(self, hass, entry, api, sid):
        super().__init__(hass, entry, api, sid, "live", LIVE_INTERVAL_S)

    async def _fetch(self):
        return await self.api.live(self.sid)


class TotalsCoordinator(_Base):
    def __init__(self, hass, entry, api, sid):
        super().__init__(hass, entry, api, sid, "totals", TOTALS_INTERVAL_S)

    async def _fetch(self):
        return await self.api.station_real_data(self.sid)
