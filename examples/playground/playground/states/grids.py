"""Grid data for the gridjs table and the glide data editor."""

import reflex as rx

from playground.seed import product_rows

GRID_ROWS = 40
GRID_COLUMNS = ("id", "name", "category", "stock")
EDITOR_COLUMNS = [{"title": column, "type": "str"} for column in GRID_COLUMNS]


def grid_rows() -> list[list[str]]:
    """Take the first seed rows as grid rows.

    Returns:
        ``GRID_ROWS`` rows of the ``GRID_COLUMNS`` values, as text: the data
        editor's text cells take strings.
    """
    return [
        [str(row[column]) for column in GRID_COLUMNS] for row in product_rows(GRID_ROWS)
    ]


class GridState(rx.State):
    """The rows both grids show, which the data editor changes."""

    rows: rx.Field[list[list[str]]] = rx.field(default_factory=grid_rows)
    edits: int = 0

    @rx.event
    def edit_cell(self, position: tuple[int, int], cell: dict):
        """Store an edited cell, editing one item of a nested list.

        Args:
            position: The cell's column and row.
            cell: The new cell; its ``data`` is the value.
        """
        column, row = position
        self.rows[row][column] = str(cell.get("data", ""))
        self.edits += 1

    @rx.event
    def reset_rows(self):
        """Undo every edit."""
        self.rows = grid_rows()
        self.edits = 0
