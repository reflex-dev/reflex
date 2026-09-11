"""A project-local module that rxconfig.py imports (the #6933 shape)."""

import os
import threading

APP_NAME = "cfgapp"
LOADS = []


def note_load() -> None:
    """Record that this sibling module was (re)imported."""
    with open(os.path.join(os.path.dirname(__file__), "sibling_imports.log"), "a") as f:
        f.write(f"sibling import thread={threading.current_thread().name} pid={os.getpid()}\n")


note_load()
