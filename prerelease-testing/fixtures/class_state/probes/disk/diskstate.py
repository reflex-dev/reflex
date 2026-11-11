"""Identical state source on every version (like the fleet app)."""
import reflex as rx


class DiskFleet(rx.State):
    count: int = 5
    user: str = ""
    history: list[str] = []
    _visits: int = 0


class DiskChild(DiskFleet):
    note: str = "fresh"
