"""This module contains the dataclasses representing the router object."""

import dataclasses
from typing import Optional

from reflex import constants
from reflex.utils import format


@dataclasses.dataclass(frozen=True)
class HeaderData:
    """An object containing headers data."""

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

    def __init__(self, router_data: Optional[dict] = None):
        """Initalize the HeaderData object based on router_data.

        Args:
            router_data: the router_data dict.
        """
        if router_data:
            for k, v in router_data.get(constants.RouteVar.HEADERS, {}).items():
                object.__setattr__(self, format.to_snake_case(k), v)
        else:
            for k in dataclasses.fields(self):
                object.__setattr__(self, k.name, "")


@dataclasses.dataclass(frozen=True)
class PageData:
    """An object containing page data."""

    host: str = ""  # repeated with self.headers.origin (remove or keep the duplicate?)
    path: str = ""
    raw_path: str = ""
    full_path: str = ""
    full_raw_path: str = ""
    params: dict = dataclasses.field(default_factory=dict)

    def __init__(self, router_data: Optional[dict] = None):
        """Initalize the PageData object based on router_data.

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

    def __init__(self, router_data: Optional[dict] = None):
        """Initalize the SessionData object based on router_data.

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

    def __init__(self, router_data: Optional[dict] = None):
        """Initialize the RouterData object.

        Args:
            router_data: the router_data dict.
        """
        object.__setattr__(self, "session", SessionData(router_data))
        object.__setattr__(self, "headers", HeaderData(router_data))
        object.__setattr__(self, "page", PageData(router_data))
