"""Gunicorn worker carrying the Reflex websocket settings into uvicorn.

Gunicorn takes no uvicorn options on its command line, so the production
backend passes them through a worker class instead. Imported by dotted path
from the gunicorn process; nothing else imports it, which keeps the optional
uvicorn dependency optional.
"""

from __future__ import annotations

from uvicorn.workers import UvicornH11Worker

from reflex.utils.exec import uvicorn_websocket_options


class ReflexUvicornWorker(UvicornH11Worker):
    """Uvicorn worker applying the app's websocket message policy."""

    CONFIG_KWARGS = {
        **UvicornH11Worker.CONFIG_KWARGS,
        **uvicorn_websocket_options(),
    }
