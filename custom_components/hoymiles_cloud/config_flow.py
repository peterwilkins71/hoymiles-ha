from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HoymilesAuthError, HoymilesCloud, HoymilesError
from .const import CONF_STATION_ID, CONF_STATION_NAME, DOMAIN

CREDS_SCHEMA = vol.Schema({vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str})


class HoymilesCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._creds: dict[str, str] = {}
        self._stations: dict[str, str] = {}

    async def _check(self, username: str, password: str) -> tuple[str | None, list[dict[str, Any]]]:
        api = HoymilesCloud(async_get_clientsession(self.hass), username, password)
        try:
            await api.login()
            return None, await api.stations()
        except HoymilesAuthError:
            return "invalid_auth", []
        except (HoymilesError, aiohttp.ClientError, TimeoutError):
            return "cannot_connect", []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            error, stations = await self._check(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            if error:
                errors["base"] = error
            elif not stations:
                errors["base"] = "no_stations"
            else:
                self._creds = user_input
                self._stations = {str(s["id"]): s.get("name") or str(s["id"]) for s in stations}
                if len(self._stations) == 1:
                    return await self.async_step_station({CONF_STATION_ID: next(iter(self._stations))})
                return await self.async_step_station()
        return self.async_show_form(step_id="user", data_schema=CREDS_SCHEMA, errors=errors)

    async def async_step_station(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            sid = user_input[CONF_STATION_ID]
            await self.async_set_unique_id(sid)
            self._abort_if_unique_id_configured()
            name = self._stations.get(sid, sid)
            return self.async_create_entry(
                title=f"Hoymiles {name}",
                data={**self._creds, CONF_STATION_ID: int(sid), CONF_STATION_NAME: name},
            )
        return self.async_show_form(
            step_id="station",
            data_schema=vol.Schema({vol.Required(CONF_STATION_ID): vol.In(self._stations)}),
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            error, _ = await self._check(entry.data[CONF_USERNAME], user_input[CONF_PASSWORD])
            if not error:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )
