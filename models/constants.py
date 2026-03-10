import asyncio

from aiohttp import ClientSession, ClientError
from json import load, loads
from pathlib import Path
from base64 import b64decode
from utils.kiwiapi import API_URL, API_ENABLED
from utils.logger import log

files_cache = {}


def _load_local_data():
    data_path = Path("data")
    files_data = [
        str(x.relative_to(data_path)) for x in data_path.rglob("*") if x.is_file()
    ]
    files_cache.update(
        {
            path.replace("\\", "/"): load(
                open(data_path.joinpath(path), encoding="utf-8")
            )
            for path in files_data
        }
    )


def _load_local_locales():
    locales_path = Path("locales")
    files_data = [
        str(x.relative_to(locales_path)) for x in locales_path.rglob("*") if x.is_file()
    ]
    files_cache.update(
        {
            path.replace("\\", "/"): locales_path.joinpath(path).read_text(
                encoding="utf-8"
            )
            for path in files_data
        }
    )


async def fetch_files(local_data=False, local_locales=False):
    if not API_ENABLED:
        files_cache.clear()
        _load_local_data()
        _load_local_locales()
        return files_cache
    async with ClientSession() as session:
        # Load data files
        files_cache.clear()
        if not local_data:
            fail = False
            try:
                response = await session.get(
                    f"{API_URL}/stats/get_data", timeout=60
                )
                if response.status != 200:
                    log("Network").error(
                        f"Failed to fetch data files, response code: {response.status}"
                    )
                    fail = True
            except (asyncio.TimeoutError, ClientError, OSError) as exc:
                log("Network").error(f"Failed to fetch data files: {exc}")
                fail = True
            if fail:
                _load_local_data()
            else:
                files_data = await response.json()
                for path, data in files_data.items():
                    files_cache[path] = loads(b64decode(data).decode("utf-8"))
        else:
            _load_local_data()
        # Load localization files
        if not local_locales:
            fail = False
            try:
                response = await session.get(
                    f"{API_URL}/misc/locales", timeout=60
                )
                if response.status != 200:
                    log("Network").error(
                        f"Failed to fetch locale files, response code: {response.status}"
                    )
                    fail = True
            except (asyncio.TimeoutError, ClientError, OSError) as exc:
                log("Network").error(f"Failed to fetch locale files: {exc}")
                fail = True
            if fail:
                _load_local_locales()
            else:
                files_data = await response.json()
                for path, data in files_data.items():
                    files_cache[path] = b64decode(data).decode("utf-8")
        else:
            _load_local_locales()
        return files_cache
