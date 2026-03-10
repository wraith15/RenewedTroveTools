import asyncio
import os
from datetime import datetime, UTC
from enum import Enum
from typing import Union, Optional
from urllib.parse import urlencode, urlsplit, urlunsplit

from aiohttp import ClientSession, ClientError
from pydantic import BaseModel, Field, validator
import platform

API_BASE_URL = os.getenv("RTT_API_BASE_URL", "").rstrip("/")
API_ENABLED = bool(API_BASE_URL)
API_DISABLED_REASON = os.getenv(
    "RTT_API_DISABLED_REASON",
    "Online API features are temporarily disabled while this fork prepares its own backend.",
)
API_VERSION = 1
API_URL = f"{API_BASE_URL}/v{API_VERSION}" if API_ENABLED else ""
SERVICE_SUBDOMAINS = ("kiwiapi", "api", "app", "trove", "trovetools", "events")


def _derive_service_url(base_url: str, subdomain: str, scheme: Optional[str] = None):
    parsed = urlsplit(base_url)
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    final_scheme = scheme or parsed.scheme

    derived_host = hostname
    for service_name in SERVICE_SUBDOMAINS:
        prefix = f"{service_name}."
        if hostname.startswith(prefix):
            derived_host = f"{subdomain}.{hostname.removeprefix(prefix)}"
            break

    return urlunsplit((final_scheme, f"{derived_host}{port}", "", "", "")).rstrip("/")


PUBLIC_BASE_URL = os.getenv(
    "RTT_PUBLIC_BASE_URL", _derive_service_url(API_BASE_URL, "app") if API_ENABLED else ""
)
WEB_URL = os.getenv("RTT_WEB_URL", PUBLIC_BASE_URL)
TROVE_WEB_URL = os.getenv(
    "RTT_TROVE_WEB_URL",
    _derive_service_url(PUBLIC_BASE_URL, "trove") if PUBLIC_BASE_URL else "",
)
TROVETOOLS_WEB_URL = os.getenv(
    "RTT_TROVETOOLS_WEB_URL",
    _derive_service_url(PUBLIC_BASE_URL, "trovetools") if PUBLIC_BASE_URL else "",
)
WS_EVENTS_URL = os.getenv(
    "RTT_EVENTS_URL",
    _derive_service_url(API_BASE_URL, "events", scheme="wss") + "/"
    if API_ENABLED
    else "",
)


class ModFileType(Enum):
    TMOD = "tmod"
    ZIP = "zip"
    CONFIG = "config"


class ModFile(BaseModel):
    file_id: int = Field(alias="fileid")
    type: ModFileType = Field(alias="format")
    is_config: bool = Field(alias="extra", default=False)
    version: str
    changes: str
    created_at: Union[int, datetime] = Field(alias="date")
    downloads: int
    size: int = Field(alias="fileid")
    hash: str = Field(default="")

    @validator("created_at")
    def parse_timestamp(cls, value):
        if isinstance(value, datetime):
            return value
        return datetime.utcfromtimestamp(value)

    @validator("version")
    def parse_version(cls, value, values):
        if values["is_config"]:
            return "config"
        if not value.strip():
            return f"File: [{str(values['file_id'])}]"
        return value


class ModAuthorRoleColors(Enum):
    null = "#6C757D"
    modder = "#198754"
    artist = "#0D6EFD"
    gold = "#FFC107"
    creator = "#328282"
    streamer = "#800080"
    admin = "#800000"


class ModAuthorRole(Enum):
    null = ""
    modder = "Modder"
    artist = "Artist"
    gold = "Gold"
    creator = "Creator"
    streamer = "Streamer"
    admin = "Admin"


class ModAuthor(BaseModel):
    ID: Optional[int]
    Username: Optional[str]
    Avatar: str
    Role: ModAuthorRole

    @property
    def avatar_url(self):
        if self.Avatar.startswith("//"):
            return f"https:{self.Avatar}"
        return self.Avatar.replace("http:", "https:")


class Mod(BaseModel):
    id: int
    name: str
    type: str
    subtype: str
    description: str
    created_at: datetime = Field(alias="date")
    views: int
    replacements: str = Field(alias="replaces")
    downloads: int = Field(alias="totaldownloads")
    thumbnail_url: str = Field(alias="image")
    notes: str
    likes: int
    authors: list[ModAuthor]
    image_url: str = Field(alias="image_full")
    file_objs: list[ModFile] = Field(alias="downloads", default_factory=list)
    installed: bool = False
    installed_file: ModFile = None
    obsolete: int

    def __contains__(self, item):
        return item in self.hashes

    @property
    def hashes(self):
        return [file.hash for file in self.file_objs]

    @validator("created_at")
    def parse_timestamp(cls, value):
        if isinstance(value, datetime):
            return value
        return datetime.fromtimestamp(value, UTC)

    @property
    def url(self):
        return f"https://trovesaurus.com/mod={self.id}"

    @property
    def image_thumbnail_url(self):
        return self.image_url.replace("_l.", "_t.")

    @property
    def is_obsolete(self):
        return self.obsolete != 0


class ImageSize(Enum):
    MINI = 24
    TINY = 32
    SMALL = 64
    MEDIUM = 128
    LARGE = 256
    HUGE = 512
    MAX = 1024


class Endpoints(Enum):
    handshake: str = "/misc/handshake"
    mods: str = "/mods"
    mods_search: str = "/mods/search"
    mod_types: str = "/mods/types"
    mod_sub_types: str = "/mods/sub_types"
    image_resize: str = "/image/resize"
    mastery: str = "/stats/mastery"
    profiles: str = "/profile"
    twitch_streams: str = "/misc/twitch_streams"
    star_chart_presets: str = "/star_chart/presets"


class KiwiAPI:
    base_url: str = API_BASE_URL
    enabled: bool = API_ENABLED
    api_version: int = API_VERSION
    api_url: str = f"{base_url}/v{api_version}" if enabled else ""

    async def handshake(self, page):
        if not self.api_url:
            return
        async with ClientSession() as session:
            try:
                await session.get(
                    f"{self.api_url}{Endpoints.handshake.value}",
                    json={
                        "version": page.metadata.version,
                        "dev": page.metadata.dev,
                        "os": {
                            "name": platform.system(),
                            "version": platform.version(),
                            "release": platform.release(),
                        },
                    },
                    timeout=5
                )
            except (asyncio.TimeoutError, ClientError, OSError):
                ...

    async def get_mods_page_count(
        self,
        page_size: int = 8,
        query: str = None,
        type: str = None,
        sub_type: str = None,
    ):
        if not self.api_url:
            return 0
        if not hasattr(self, "_mod_pages_count"):
            self._mod_pages_count = {}
        params = {"limit": page_size}
        if query is not None:
            params["query"] = query
        if type is not None:
            params["type"] = type
        if sub_type is not None:
            params["sub_type"] = sub_type
        encoded_params = urlencode(params)
        cached_pages = self._mod_pages_count.get(encoded_params)
        if cached_pages is None:
            async with ClientSession() as session:
                try:
                    async with session.get(
                        f"{self.api_url}{Endpoints.mods_search.value}?{encoded_params}"
                    ) as response:
                        count = int(response.headers.get("count", 0))
                        cached_pages = count // page_size + 1 if count else 0
                        self._mod_pages_count[encoded_params] = cached_pages
                except (asyncio.TimeoutError, ClientError, OSError):
                    cached_pages = 0
        return cached_pages

    async def get_mods_list_chunk(
        self,
        page_size: int = 8,
        page: int = 0,
        query: str = None,
        type: str = None,
        sub_type: str = None,
        sort_by: list[tuple[str, str]] = None,
    ):
        if not self.api_url:
            return []
        if not hasattr(self, "_mod_pages"):
            self._mod_pages = {}
        offset = page_size * page
        params = {"limit": page_size, "offset": offset}
        if query is not None:
            params["query"] = query
        if type is not None:
            params["type"] = type
        if sub_type is not None:
            params["sub_type"] = sub_type
        if sort_by is not None:
            sort_by_string = ",".join([f"{field}:{order}" for field, order in sort_by])
            params["sort_by"] = sort_by_string
        encoded_params = urlencode(params)
        cached_mods = self._mod_pages.get(encoded_params)
        if cached_mods is None:
            async with ClientSession() as session:
                try:
                    async with session.get(
                        f"{self.api_url}{Endpoints.mods_search.value}?{encoded_params}"
                    ) as response:
                        cached_mods = await response.json()
                        cached_mods = [Mod(**mod) for mod in cached_mods]
                        self._mod_pages[encoded_params] = cached_mods
                except (asyncio.TimeoutError, ClientError, OSError):
                    cached_mods = []
        return cached_mods

    async def get_mod_types(self):
        if not self.api_url:
            self._mod_types = []
            return self._mod_types
        if not hasattr(self, "_mod_types"):
            async with ClientSession() as session:
                try:
                    async with session.get(
                        f"{self.api_url}{Endpoints.mod_types.value}"
                    ) as response:
                        self._mod_types = await response.json()
                        return self._mod_types
                except (asyncio.TimeoutError, ClientError, OSError):
                    self._mod_types = []
        return self._mod_types

    async def get_mod_sub_types(self, type: str):
        if not self.api_url:
            if not hasattr(self, "_mod_sub_types"):
                self._mod_sub_types = {}
            self._mod_sub_types[type] = []
            return self._mod_sub_types[type]
        if not hasattr(self, "_mod_sub_types") or self._mod_sub_types.get(type) is None:
            async with ClientSession() as session:
                try:
                    async with session.get(
                        f"{self.api_url}{Endpoints.mod_sub_types.value}/{type}"
                    ) as response:
                        if not hasattr(self, "_mod_sub_types"):
                            self._mod_sub_types = {}
                        self._mod_sub_types[type] = await response.json()
                        return self._mod_sub_types[type]
                except (asyncio.TimeoutError, ClientError, OSError):
                    if not hasattr(self, "_mod_sub_types"):
                        self._mod_sub_types = {}
                    self._mod_sub_types[type] = []
        return self._mod_sub_types[type]

    def get_resized_image_url(self, url: str, size: ImageSize):
        if not self.api_url:
            return url
        return (
            self.api_url + Endpoints.image_resize.value + f"?url={url}&size={size.name}"
        )

    async def get_mastery(self):
        if not self.api_url:
            return None
        async with ClientSession() as session:
            try:
                async with session.get(
                    f"{self.api_url}{Endpoints.mastery.value}"
                ) as response:
                    if response.status != 200:
                        return
                    return await response.json()
            except (asyncio.TimeoutError, ClientError, OSError):
                return

    async def update_mastery(self, user_token: str, mastery_data: dict):
        if not self.api_url:
            return
        async with ClientSession() as session:
            await session.put(
                f"{self.api_url}{Endpoints.mastery.value}",
                headers={"Authorization": user_token},
                json={"mastery_data": mastery_data},
            )

    async def create_profile(self, user_token: str, name: str, description: str):
        if not self.api_url:
            return
        async with ClientSession() as session:
            await session.post(
                f"{self.api_url}{Endpoints.profiles.value}/create",
                headers={"Authorization": user_token},
                json={"name": name, "description": description},
            )

    async def update_profile(self, user_token: str, profile_id: str, **kwargs):
        if not self.api_url:
            return
        async with ClientSession() as session:
            await session.put(
                f"{self.api_url}{Endpoints.profiles.value}/update/{profile_id}",
                headers={"Authorization": user_token},
                json=kwargs,
            )

    async def list_profiles(self, user_token: str):
        if not self.api_url:
            return []
        async with ClientSession() as session:
            try:
                async with session.get(
                    f"{self.api_url}{Endpoints.profiles.value}/list_profiles",
                    headers={"Authorization": user_token},
                ) as response:
                    return await response.json()
            except (asyncio.TimeoutError, ClientError, OSError):
                return []

    async def share_profile(self, user_token: str, profile_id: str):
        if not self.api_url:
            return
        async with ClientSession() as session:
            await session.post(
                f"{self.api_url}{Endpoints.profiles.value}/share/{profile_id}",
                headers={"Authorization": user_token},
            )

    async def private_profile(self, user_token: str, profile_id: str):
        if not self.api_url:
            return
        async with ClientSession() as session:
            await session.post(
                f"{self.api_url}{Endpoints.profiles.value}/unshare/{profile_id}",
                headers={"Authorization": user_token},
            )

    async def delete_profile(self, user_token: str, profile_id: str):
        if not self.api_url:
            return
        async with ClientSession() as session:
            await session.delete(
                f"{self.api_url}{Endpoints.profiles.value}/delete/{profile_id}",
                headers={"Authorization": user_token},
            )

    async def add_mods_to_profile(
        self, user_token: str, profile_id: str, mod_hashes: list[str]
    ):
        if not self.api_url:
            return
        async with ClientSession() as session:
            await session.post(
                f"{self.api_url}{Endpoints.profiles.value}/mod_hashes/{profile_id}",
                headers={"Authorization": user_token},
                json={"hashes": mod_hashes},
            )

    async def remove_mods_from_profile(
        self, user_token: str, profile_id: str, mod_hashes: list[str]
    ):
        if not self.api_url:
            return
        async with ClientSession() as session:
            await session.delete(
                f"{self.api_url}{Endpoints.profiles.value}/mod_hashes/{profile_id}",
                headers={"Authorization": user_token},
                json={"hashes": mod_hashes},
            )

    async def get_twitch_streams(self):
        if not self.api_url:
            return []
        async with ClientSession() as session:
            try:
                async with session.get(
                    f"{self.api_url}{Endpoints.twitch_streams.value}"
                ) as response:
                    if response.status != 200:
                        return []
                    return await response.json()
            except Exception:
                return []

    async def get_star_chart_presets(self):
        if not self.api_url:
            return []
        async with ClientSession() as session:
            try:
                response = await session.get(
                    f"{self.api_url}{Endpoints.star_chart_presets.value}",
                    timeout=5
                )
                if response.status != 200:
                    return []
            except (asyncio.TimeoutError, ClientError, OSError):
                return []
            return sorted(await response.json(), key=lambda x: x["preset"]["order"])


class ModProfileList:
    def __init__(self, mod_profiles: list[dict]):
        self._profiles = mod_profiles

    def __iter__(self):
        return iter(self.profiles)

    @property
    def profiles(self):
        return self._profiles

    @property
    def all_profile_mods(self):
        return [mod for m in self._profiles for mod in m["mods"]]

    @property
    def hashes(self):
        return list(set([m["hash"] for m in self.all_profile_mods]))

    async def trovesaurus_data(self):
        if not API_ENABLED or not self.hashes:
            return {}
        async with ClientSession() as session:
            try:
                response = await session.get(
                    f"{API_URL}/mods/hashes",
                    json={"hashes": self.hashes},
                    timeout=10
                )
                if response.status == 200:
                    return await response.json()
            except (asyncio.TimeoutError, ClientError, OSError):
                ...
            return {}

    async def update_trovesaurus_data(self):
        trovesaurus_data = await self.trovesaurus_data()
        for mod in self.all_profile_mods:
            if "trovesaurus_data" not in mod:
                mod["trovesaurus_data"] = None
            for ts_mod, data in trovesaurus_data.items():
                if data is None:
                    continue
                if mod["hash"] == ts_mod:
                    mod["trovesaurus_data"] = data
                    downloads = data["downloads"]
                    downloads.sort(key=lambda x: x["date"], reverse=True)
                    mod["current_version"] = [
                        f for f in downloads if f["hash"] == ts_mod
                    ][0]
                    mod["update"] = downloads[0]
                    mod["has_update"] = mod["update"] != mod["current_version"]
