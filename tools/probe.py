# /// script
# requires-python = ">=3.12"
# dependencies = ["aiohttp", "argon2-cffi"]
# ///
"""Log in and print one reading, to check the API client before installing it in HA.

    uv run tools/probe.py you@example.com
"""
import asyncio
import getpass
import json
import sys
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "hoymiles_cloud"))
from api import HoymilesCloud  # noqa: E402


async def main(user: str) -> None:
    password = getpass.getpass("S-Miles password: ")
    async with aiohttp.ClientSession() as session:
        api = HoymilesCloud(session, user, password)
        await api.login()
        print("login ok")
        for s in await api.stations():
            sid = s["id"]
            print(f"\nstation {sid}")
            totals = await api.station_real_data(sid)
            print(json.dumps({k: totals.get(k) for k in
                              ("real_power", "today_eq", "month_eq", "year_eq", "total_eq", "data_time")}, indent=2))
            live = await api.live(sid)
            print(json.dumps({"t": live.get("t"), "power": live.get("power")}, indent=2))


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else input("S-Miles login: ")))
