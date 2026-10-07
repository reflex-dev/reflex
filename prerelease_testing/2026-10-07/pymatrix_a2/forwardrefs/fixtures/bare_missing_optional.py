"""Forgotten model import with bare annotations and a optional field."""

import reflex as rx
from fixtures.origin import check_origin

check_origin()


class Warehouse(rx.State):
    """Invalid app: the model import is deliberately omitted."""

    selection: InventoryItem | None = None  # noqa: F821 - deliberate missing model import.
