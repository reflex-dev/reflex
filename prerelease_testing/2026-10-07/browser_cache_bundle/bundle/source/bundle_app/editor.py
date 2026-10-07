"""Optional catalog editor and syntax-highlighted query example."""

import json
from typing import Any
import reflex as rx
from .common import shell


class CatalogState(rx.State):
    """Small independent catalog state."""

    rows: list[list[Any]] = [["Notebook", 24], ["Pencil", 80], ["Folder", 45]]
    edit_count: int = 0
    last_edit: str = ""

    @rx.event
    def edit(self, position: tuple[int, int], cell: dict[str, Any]):
        """Persist an edited catalog cell.

        Args:
            position: Column and row index.
            cell: Glide cell payload.
        """
        column, row = position
        self.rows[row][column] = cell["data"]
        self.edit_count += 1
        self.last_edit = json.dumps(self.rows[row])


def editor() -> rx.Component:
    """Build the catalog route.

    Returns:
        Editable grid plus a query snippet.
    """
    return shell(
        "Catalog editor",
        rx.text(CatalogState.edit_count, id="edit-count"),
        rx.text(CatalogState.last_edit, id="last-edit"),
        rx.box(
            rx.data_editor(
                columns=[
                    {"title": "Product", "type": "str", "width": 180},
                    {"title": "Stock", "type": "int", "width": 90},
                ],
                data=CatalogState.rows,
                on_cell_edited=CatalogState.edit,
                width="500px",
                height="190px",
            ),
            id="catalog-grid",
            width="500px",
            height="190px",
        ),
        rx.code_block(
            "SELECT product, stock FROM catalog WHERE stock < 50;",
            language="sql",
            id="query-example",
        ),
    )
