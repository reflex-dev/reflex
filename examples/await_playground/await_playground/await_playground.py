"""Playground for awaiting browser script results in background handlers."""

import reflex as rx

from . import (  # noqa: F401  registers pages
    basics,
    concurrent,
    dialogs,
    disconnect,
    errors,
)

app = rx.App()
