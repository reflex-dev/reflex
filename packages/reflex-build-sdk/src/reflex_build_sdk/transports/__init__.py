"""Transports that send the Reflex Build clients' requests over HTTP.

Unless a transport is passed in, ``AsyncReflexBuild`` uses the first installed of
``AiohttpTransport``, ``AsyncHttpx2Transport`` and ``AsyncHttpxTransport``, and
``ReflexBuild`` uses ``Httpx2Transport``, or ``HttpxTransport`` if httpx2 is not
installed. Implement ``Transport`` or ``AsyncTransport`` to send
requests through another HTTP library.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from reflex_build_sdk.transports._aiohttp import AiohttpTransport
from reflex_build_sdk.transports._base import (
    AsyncTransport,
    Request,
    Response,
    Transport,
    TransportError,
)

if TYPE_CHECKING:
    from reflex_build_sdk.transports._httpx import AsyncHttpxTransport, HttpxTransport
    from reflex_build_sdk.transports._httpx2 import (
        AsyncHttpx2Transport,
        Httpx2Transport,
    )

# The transports importing an optional library, by name, with their module.
_LAZY = {
    "AsyncHttpxTransport": "_httpx",
    "HttpxTransport": "_httpx",
    "AsyncHttpx2Transport": "_httpx2",
    "Httpx2Transport": "_httpx2",
}

__all__ = [
    "AiohttpTransport",
    "AsyncHttpx2Transport",
    "AsyncHttpxTransport",
    "AsyncTransport",
    "Httpx2Transport",
    "HttpxTransport",
    "Request",
    "Response",
    "Transport",
    "TransportError",
]


def __getattr__(name: str) -> object:
    """Import the httpx and httpx2 transports on first access, as both are optional.

    Args:
        name: The attribute's name.

    Returns:
        The transport of that name.

    Raises:
        AttributeError: If the module has no such attribute.
    """
    module = _LAZY.get(name)
    if module is not None:
        return getattr(importlib.import_module(f"{__name__}.{module}"), name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
