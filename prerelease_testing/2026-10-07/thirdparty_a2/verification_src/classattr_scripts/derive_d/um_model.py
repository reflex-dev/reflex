"""A user module defining an rx.Model subclass (imported, so import-machinery frames sit above it)."""

import reflex as rx


class UserModelInModule(rx.Model, table=True):  # line 6
    y: int = 0
