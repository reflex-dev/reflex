"""The transport each client uses when none is passed in.

aiohttp, httpx2 and httpx are optional, so the default is picked from what is
installed, and each is imported only once a client needs it.
"""

from __future__ import annotations

from importlib.util import find_spec
from typing import NoReturn

from reflex_build_sdk.transports._base import AsyncTransport, Transport


def _raise_missing(client: str, extra: str) -> NoReturn:
    msg = (
        f"{client} needs an HTTP library to send requests: install "
        f"reflex-build-sdk[{extra}], or pass a transport."
    )
    raise ImportError(msg)


def default_transport() -> Transport:
    """Create the transport ``ReflexBuild`` uses when none is passed in.

    Returns:
        A transport sending requests with httpx2, or with httpx if httpx2 is not
        installed.

    Raises:
        ImportError: If neither httpx2 nor httpx is installed.
    """
    if find_spec("httpx2") is not None:
        from reflex_build_sdk.transports._httpx2 import Httpx2Transport

        return Httpx2Transport()
    if find_spec("httpx") is not None:
        from reflex_build_sdk.transports._httpx import HttpxTransport

        return HttpxTransport()
    _raise_missing("ReflexBuild", "httpx2")


def async_default_transport() -> AsyncTransport:
    """Create the transport ``AsyncReflexBuild`` uses when none is passed in.

    Returns:
        A transport sending requests with the first of aiohttp, httpx2 and httpx
        that is installed.

    Raises:
        ImportError: If none of aiohttp, httpx2 and httpx is installed.
    """
    if find_spec("aiohttp") is not None:
        from reflex_build_sdk.transports._aiohttp import AiohttpTransport

        return AiohttpTransport()
    if find_spec("httpx2") is not None:
        from reflex_build_sdk.transports._httpx2 import AsyncHttpx2Transport

        return AsyncHttpx2Transport()
    if find_spec("httpx") is not None:
        from reflex_build_sdk.transports._httpx import AsyncHttpxTransport

        return AsyncHttpxTransport()
    _raise_missing("AsyncReflexBuild", "aiohttp")
