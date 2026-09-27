"""Async client for the Hoymiles S-Miles Cloud web API.

Reverse engineered from the global.hoymiles.com web app (2026-09). Login:

1. POST /iam/pub/3/auth/pre-insp {"u": user}
   -> data {n: nonce, a: salt hex, v: hash version, dc: data centre}
2. Hash the password:
   v 1/2: md5hex(pw) + "." + base64(sha256(pw))
   v 3:   argon2id(pw, salt=bytes.fromhex(a), t=3, m=32 MiB, p=1, len=32) as hex
3. POST /iam/pub/3/auth/login {"u": user, "ch": hash, "n": nonce}
   -> data {token}

Every other call is a POST with the raw token in the ``authorization`` header.
The API answers HTTP 200 even on failure; ``status`` is "0" on success and a
stale token reads {"status": "1", "message": "token error,please Re-login."}.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import time
from typing import Any

import aiohttp
from argon2.low_level import Type, hash_secret_raw

_LOGGER = logging.getLogger(__name__)

HOST_GLOBAL = "https://neapi.hoymiles.com"
HOST_EU = "https://euapi.hoymiles.com"
DC_EU = 1

TIMEOUT = aiohttp.ClientTimeout(total=30)
# Minimum gap between live-session renewals when the station gives no live data.
BURST_RENEW_MIN_S = 60


class HoymilesError(Exception):
    """The API answered, but not with success."""


class HoymilesAuthError(HoymilesError):
    """Bad credentials, or the token could not be renewed."""


def hash_password(password: str, version: int, salt_hex: str | None) -> str:
    if version == 3:
        if not salt_hex:
            raise HoymilesAuthError("Login pre-check returned no salt")
        raw = hash_secret_raw(
            secret=password.encode(),
            salt=bytes.fromhex(salt_hex),
            time_cost=3,
            memory_cost=32768,  # KiB, matching hash-wasm's memorySize
            parallelism=1,
            hash_len=32,
            type=Type.ID,
        )
        return raw.hex()
    md5 = hashlib.md5(password.encode()).hexdigest()  # noqa: S324 - the API's scheme
    sha = base64.b64encode(hashlib.sha256(password.encode()).digest()).decode()
    return f"{md5}.{sha}"


def _is_token_error(body: dict[str, Any]) -> bool:
    return str(body.get("status")) != "0" and "token" in str(body.get("message", "")).lower()


class HoymilesCloud:
    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._token: str | None = None
        self._burst_uri: dict[int, str] = {}
        self._burst_renewed: dict[int, float] = {}

    async def _post(self, url: str, payload: dict[str, Any], auth: bool = True) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if auth and self._token:
            headers["authorization"] = self._token
        async with self._session.post(url, json=payload, headers=headers, timeout=TIMEOUT) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def login(self) -> None:
        pre = await self._post(f"{HOST_GLOBAL}/iam/pub/3/auth/pre-insp", {"u": self._username}, auth=False)
        data = pre.get("data") or {}
        if str(pre.get("status")) != "0" or data.get("v") == -1:
            raise HoymilesAuthError(pre.get("message") or "Unknown account")
        if data.get("f") == 1:
            raise HoymilesAuthError("Hoymiles requires a password reset; log in on the website first")

        body = {
            "u": self._username,
            "ch": hash_password(self._password, int(data.get("v", 3)), data.get("a")),
            "n": data.get("n"),
        }
        # The web app switches to the EU host for dc=1 accounts; fall back to the
        # global host in case that routing changes.
        hosts = [HOST_EU, HOST_GLOBAL] if data.get("dc") == DC_EU else [HOST_GLOBAL, HOST_EU]
        last: dict[str, Any] | Exception = {}
        for host in hosts:
            try:
                res = await self._post(f"{host}/iam/pub/3/auth/login", body, auth=False)
            except aiohttp.ClientResponseError as err:
                last = err
                continue
            token = (res.get("data") or {}).get("token") if str(res.get("status")) == "0" else None
            if token:
                self._token = token
                self._burst_uri.clear()
                return
            last = res
            # A clear credential rejection will not improve on the other host.
            if res.get("status") is not None:
                break
        msg = last.get("message") if isinstance(last, dict) else str(last)
        raise HoymilesAuthError(msg or "Login failed")

    async def _call(self, url: str, payload: dict[str, Any]) -> Any:
        """POST with the token, logging in again once if it has expired."""
        if not self._token:
            await self.login()
        body = await self._post(url, payload)
        if _is_token_error(body):
            _LOGGER.debug("Hoymiles token expired, logging in again")
            await self.login()
            body = await self._post(url, payload)
        if str(body.get("status")) != "0":
            if _is_token_error(body):
                raise HoymilesAuthError(body.get("message"))
            raise HoymilesError(body.get("message") or f"API error on {url}")
        return body.get("data")

    async def stations(self) -> list[dict[str, Any]]:
        data = await self._call(f"{HOST_GLOBAL}/pvm/api/0/station/select_by_page", {"page": 1, "page_size": 100})
        return list((data or {}).get("list") or [])

    async def station_real_data(self, sid: int) -> dict[str, Any]:
        """Energy totals and power, refreshed by the cloud every ~5-15 minutes."""
        return await self._call(
            f"{HOST_GLOBAL}/pvm-data/api/0/station/data/count_station_real_data", {"sid": sid}
        ) or {}

    async def _new_burst_uri(self, sid: int) -> str:
        """Ask for a fresh live-data URI, which also starts a new live session."""
        data = await self._call(f"{HOST_GLOBAL}/pvm/api/0/station/get_sd_uri", {"sid": sid})
        uri = (data or {}).get("uri")
        if not uri:
            raise HoymilesError("No live-data URI for station")
        self._burst_uri[sid] = uri
        self._burst_renewed[sid] = time.monotonic()
        return uri

    async def live(self, sid: int) -> dict[str, Any]:
        """Near real-time power ("burst") data: {power: {pv, pvr, ...}, flow, t, dly}.

        A live session is finite. The web app keeps polling only while a response
        carries ``dly`` (the next poll delay, in ms); once a response lacks it the
        session has ended, and later polls still return status "0" but no ``power``.
        So a reading without ``power`` means: start a new session and try again.
        """
        for attempt in range(2):
            uri = self._burst_uri.get(sid)
            if not uri or attempt:
                # Renewal starts a session on the device side; don't do it on every
                # poll if the station is genuinely not answering (e.g. at night).
                since = time.monotonic() - self._burst_renewed.get(sid, float("-inf"))
                if uri and since < BURST_RENEW_MIN_S:
                    break
                uri = await self._new_burst_uri(sid)
            try:
                body = await self._post(uri, {"m": 0, "t": 1, "reflux": 0})
            except aiohttp.ClientResponseError:
                self._burst_uri.pop(sid, None)
                if attempt:
                    raise
                continue
            if _is_token_error(body):
                await self.login()
                continue
            data = body.get("data") if str(body.get("status")) == "0" else None
            if isinstance(data, dict) and data.get("power"):
                if not data.get("dly"):
                    # Last reading of this session: renew on the next poll.
                    self._burst_uri.pop(sid, None)
                return data
            _LOGGER.debug("Live session ended for %s (response keys: %s); renewing",
                          sid, sorted(data) if isinstance(data, dict) else type(data).__name__)
        raise HoymilesError("Live data not available (is the inverter online?)")
