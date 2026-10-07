"""Forgotten model import with bare annotations and a list field."""

import reflex as rx
from fixtures.origin import check_origin

check_origin()


class Warehouse(rx.State):
    """Invalid app: the model import is deliberately omitted."""

    selection: list[InventoryItem] = []  # noqa: F821 - deliberate missing model import.


def build_page():
    """Use the missing model in an ordinary foreach page.

    Returns:
        A component if the model type can be resolved.
    """
    return rx.foreach(Warehouse.selection, lambda item: rx.text(item.sku))
