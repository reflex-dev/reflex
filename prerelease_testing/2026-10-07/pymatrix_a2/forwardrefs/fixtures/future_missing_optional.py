"""Forgotten model import with future annotations and a optional field."""

from __future__ import annotations

import reflex as rx
from fixtures.origin import check_origin

check_origin()


class Warehouse(rx.State):
    """Invalid app: the model import is deliberately omitted."""

    selection: InventoryItem | None = None  # noqa: F821 - deliberate missing model import.
