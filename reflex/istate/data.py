"""This module contains the dataclasses representing the router object."""

import dataclasses
from typing import Mapping

from reflex import constants
from reflex.utils import format
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


@dataclasses.dataclass(frozen=True, init=False)
class HeaderData(_HeaderData):
    """An object containing headers data."""

    def __init__(self, router_data: dict | None = None):
        """Initialize the HeaderData object based on router_data.

        Args:
            router_data: the router_data dict.
        """
        super().__init__()
        if router_data:
            fields_names = [f.name for f in dataclasses.fields(self)]
            for k, v in router_data.get(constants.RouteVar.HEADERS, {}).items():
                snake_case_key = format.to_snake_case(k)
                if snake_case_key in fields_names:
                    object.__setattr__(self, snake_case_key, v)
            object.__setattr__(
                self,
                "raw_headers",
                _FrozenDictStrStr(
                    **{
                        k: v
                        for k, v in router_data.get(
                            constants.RouteVar.HEADERS, {}
                        ).items()
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


@dataclasses.dataclass(frozen=True)
class PageData:
    """An object containing page data."""

    host: str = ""  # repeated with self.headers.origin (remove or keep the duplicate?)
    path: str = ""
    raw_path: str = ""
    full_path: str = ""
    full_raw_path: str = ""
    params: dict = dataclasses.field(default_factory=dict)

    def __init__(self, router_data: dict | None = None):
        """Initialize the PageData object based on router_data.

        Args:
            router_data: the router_data dict.
        """
        if router_data:
            object.__setattr__(
                self,
                "host",
                router_data.get(constants.RouteVar.HEADERS, {}).get("origin", ""),
            )
            object.__setattr__(
                self, "path", router_data.get(constants.RouteVar.PATH, "")
            )
            object.__setattr__(
                self, "raw_path", router_data.get(constants.RouteVar.ORIGIN, "")
            )
            object.__setattr__(self, "full_path", f"{self.host}{self.path}")
            object.__setattr__(self, "full_raw_path", f"{self.host}{self.raw_path}")
            object.__setattr__(
                self, "params", router_data.get(constants.RouteVar.QUERY, {})
            )
        else:
            object.__setattr__(self, "host", "")
            object.__setattr__(self, "path", "")
            object.__setattr__(self, "raw_path", "")
            object.__setattr__(self, "full_path", "")
            object.__setattr__(self, "full_raw_path", "")
            object.__setattr__(self, "params", {})


@dataclasses.dataclass(frozen=True, init=False)
class SessionData:
    """An object containing session data."""

    client_token: str = ""
    client_ip: str = ""
    session_id: str = ""

    def __init__(self, router_data: dict | None = None):
        """Initialize the SessionData object based on router_data.

        Args:
            router_data: the router_data dict.
        """
        if router_data:
            client_token = router_data.get(constants.RouteVar.CLIENT_TOKEN, "")
            client_ip = router_data.get(constants.RouteVar.CLIENT_IP, "")
            session_id = router_data.get(constants.RouteVar.SESSION_ID, "")
        else:
            client_token = client_ip = session_id = ""
        object.__setattr__(self, "client_token", client_token)
        object.__setattr__(self, "client_ip", client_ip)
        object.__setattr__(self, "session_id", session_id)


@dataclasses.dataclass(frozen=True, init=False)
class RouterData:
    """An object containing RouterData."""

    session: SessionData = dataclasses.field(default_factory=SessionData)
    headers: HeaderData = dataclasses.field(default_factory=HeaderData)
    page: PageData = dataclasses.field(default_factory=PageData)

    def __init__(self, router_data: dict | None = None):
        """Initialize the RouterData object.

        Args:
            router_data: the router_data dict.
        """
        object.__setattr__(self, "session", SessionData(router_data))
        object.__setattr__(self, "headers", HeaderData(router_data))
        object.__setattr__(self, "page", PageData(router_data))
