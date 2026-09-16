"""The transport each client uses when none is passed in.

The names differ only by the ``Async`` prefix so the synchronous client, generated
from the asynchronous one, picks up its own default.
"""

from reflex_sdk.transports._aiohttp import AiohttpTransport as AsyncDefaultTransport
from reflex_sdk.transports._httpx import HttpxTransport as DefaultTransport

__all__ = ["AsyncDefaultTransport", "DefaultTransport"]
