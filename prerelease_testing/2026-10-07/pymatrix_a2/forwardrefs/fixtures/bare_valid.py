"""Valid bare annotation control with the model already imported."""

import reflex as rx
from fixtures.models import InventoryItem
from fixtures.origin import check_origin

check_origin()


class Warehouse(rx.State):
    """Ordinary state with resolved model annotations."""

    items: list[InventoryItem] = [InventoryItem(sku="tea", stock=10)]
    selection: InventoryItem | None = None


def verify():
    """Check that both declared model field types resolved correctly.

    Returns:
        The resolved annotation strings.
    """
    assert Warehouse.items._var_type == list[InventoryItem]
    assert Warehouse.selection._var_type == InventoryItem | None
    return {
        "items": str(Warehouse.items._var_type),
        "selection": str(Warehouse.selection._var_type),
    }


def build_page():
    """Use the resolved model field in an ordinary foreach page.

    Returns:
        A valid model-backed foreach component.
    """
    return rx.foreach(Warehouse.items, lambda item: rx.text(item.sku))
