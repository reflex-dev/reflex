"""This module contains the dataclasses representing the router object."""

import dataclasses
from collections.abc import Mapping
from typing import TYPE_CHECKING
from urllib.parse import _NetlocResultMixinStr, urlsplit

from reflex import constants
from reflex.utils import console, format
from reflex.utils.serializers import serializer


@dataclasses.dataclass(frozen=True, init=False)
class _FrozenDictStrStr(Mapping[str, str]):
    _data: tuple[tuple[str, str], ...]

    def __init__(self, **kwargs):
        object.__setattr__(self, "_data", tuple(sorted(kwargs.items())))

    def __getitem__(self, key: str) -> str:
        return dict(self._data)[key]

    def __iter__(self):
        return (x[0] for x in self._data)

    def __len__(self):
        return len(self._data)


@dataclasses.dataclass(frozen=True)
class _HeaderData:
    host: str = ""
    origin: str = ""
    upgrade: str = ""
    connection: str = ""
    cookie: str = ""
    pragma: str = ""
    cache_control: str = ""
    user_agent: str = ""
    sec_websocket_version: str = ""
    sec_websocket_key: str = ""
    sec_websocket_extensions: str = ""
    accept_encoding: str = ""
    accept_language: str = ""
    raw_headers: Mapping[str, str] = dataclasses.field(
        default_factory=_FrozenDictStrStr
    )


_HEADER_DATA_FIELDS = frozenset(
    [field.name for field in dataclasses.fields(_HeaderData)]
)


@dataclasses.dataclass(frozen=True)
class HeaderData(_HeaderData):
    """An object containing headers data."""

    @classmethod
    def from_router_data(cls, router_data: dict) -> "HeaderData":
        """Create a HeaderData object from the given router_data.

        Args:
            router_data: the router_data dict.

        Returns:
            A HeaderData object initialized with the provided router_data.
        """
        return cls(
            **{
                snake_case_key: v
                for k, v in router_data.get(constants.RouteVar.HEADERS, {}).items()
                if v
                and (snake_case_key := format.to_snake_case(k)) in _HEADER_DATA_FIELDS
            },
            raw_headers=_FrozenDictStrStr(
                **{
                    k: v
                    for k, v in router_data.get(constants.RouteVar.HEADERS, {}).items()
                    if v
                }
            ),
        )


@serializer(to=dict)
def serialize_frozen_dict_str_str(obj: _FrozenDictStrStr) -> dict:
    """Serialize a _FrozenDictStrStr object to a dict.

    Args:
        obj: the _FrozenDictStrStr object.

    Returns:
        A dict representation of the _FrozenDictStrStr object.
    """
    return dict(obj._data)


class ReflexURL(str, _NetlocResultMixinStr):
    """A class representing a URL split result."""

    if TYPE_CHECKING:
        scheme: str
        netloc: str
        path: str
        query: str
        fragment: str

    def __new__(cls, url: str):
        """Create a new ReflexURL instance.

        Args:
            url: the URL to split.

        Returns:
            A new ReflexURL instance.
        """
        (scheme, netloc, path, query, fragment) = urlsplit(url)
        obj = super().__new__(cls, url)
        object.__setattr__(obj, "scheme", scheme)
        object.__setattr__(obj, "netloc", netloc)
        object.__setattr__(obj, "path", path)
        object.__setattr__(obj, "query", query)
        object.__setattr__(obj, "fragment", fragment)
        return obj


@dataclasses.dataclass(frozen=True)
class PageData:
    """An object containing page data."""

    host: str = ""  # repeated with self.headers.origin (remove or keep the duplicate?)
    path: str = ""
    raw_path: str = ""
    full_path: str = ""
    full_raw_path: str = ""
    params: dict = dataclasses.field(default_factory=dict)

    @classmethod
    def from_router_data(cls, router_data: dict) -> "PageData":
        """Create a PageData object from the given router_data.

        Args:
            router_data: the router_data dict.

        Returns:
            A PageData object initialized with the provided router_data.
        """
        host = router_data.get(constants.RouteVar.HEADERS, {}).get("origin", "")
        path = router_data.get(constants.RouteVar.PATH, "")
        raw_path = router_data.get(constants.RouteVar.ORIGIN, "")
        return cls(
            host=host,
            path=path,
            raw_path=raw_path,
            full_path=f"{host}{path}",
            full_raw_path=f"{host}{raw_path}",
            params=router_data.get(constants.RouteVar.QUERY, {}),
        )


@dataclasses.dataclass(frozen=True)
class SessionData:
    """An object containing session data."""

    client_token: str = ""
    client_ip: str = ""
    session_id: str = ""

    @classmethod
    def from_router_data(cls, router_data: dict) -> "SessionData":
        """Create a SessionData object from the given router_data.

        Args:
            router_data: the router_data dict.

        Returns:
            A SessionData object initialized with the provided router_data.
        """
        return cls(
            client_token=router_data.get(constants.RouteVar.CLIENT_TOKEN, ""),
            client_ip=router_data.get(constants.RouteVar.CLIENT_IP, ""),
            session_id=router_data.get(constants.RouteVar.SESSION_ID, ""),
        )


@dataclasses.dataclass(frozen=True)
class RouterData:
    """An object containing RouterData."""

    session: SessionData = dataclasses.field(default_factory=SessionData)
    headers: HeaderData = dataclasses.field(default_factory=HeaderData)
    _page: PageData = dataclasses.field(default_factory=PageData)
    url: ReflexURL = dataclasses.field(default=ReflexURL(""))
    route_id: str = ""

    @property
    def page(self) -> PageData:
        """Get the page data.

        Returns:
            The PageData object.
        """
        console.deprecate(
            feature_name="RouterData.page",
            reason="Use RouterData.url instead",
            deprecation_version="0.8.1",
            removal_version="0.9.0",
        )
        return self._page

    @classmethod
    def from_router_data(cls, router_data: dict) -> "RouterData":
        """Create a RouterData object from the given router_data.

        Args:
            router_data: the router_data dict.

        Returns:
            A RouterData object initialized with the provided router_data.
        """
        return cls(
            session=SessionData.from_router_data(router_data),
            headers=HeaderData.from_router_data(router_data),
            _page=PageData.from_router_data(router_data),
            url=ReflexURL(
                router_data.get(constants.RouteVar.HEADERS, {}).get("origin", "")
                + router_data.get(constants.RouteVar.ORIGIN, "")
            ),
            route_id=router_data.get(constants.RouteVar.PATH, ""),
        )


@serializer(to=dict)
def serialize_router_data(obj: RouterData) -> dict:
    """Serialize a RouterData object to a dict.

    Args:
        obj: the RouterData object.

    Returns:
        A dict representation of the RouterData object.
    """
    return {
        "session": obj.session,
        "headers": obj.headers,
        "page": obj._page,
        "url": obj.url,
        "route_id": obj.route_id,
    }
