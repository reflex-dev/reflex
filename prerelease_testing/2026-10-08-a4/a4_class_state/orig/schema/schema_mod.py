"""State whose frontend-var default comes from $SCHEMA_DEFAULT (to simulate editing a default between deploys)."""

import os

import reflex as rx


class SchemaState(rx.State):
    count: int = int(os.environ.get("SCHEMA_DEFAULT", "0"))
    label: str = "x"
    _secret: str = "be"
