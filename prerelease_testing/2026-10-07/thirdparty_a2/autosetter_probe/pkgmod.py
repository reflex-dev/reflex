from __future__ import annotations

import reflex as rx


class PkgBaseState(rx.State):
    items: list[str] = []
    note: str = ""
