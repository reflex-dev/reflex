"""Helper module imported by the app (hot-reload target)."""

import os

HELPER_VERSION = "h1"


def describe() -> str:
    return f"{HELPER_VERSION} pid={os.getpid()}"
