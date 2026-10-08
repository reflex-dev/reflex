"""Rendering switches: rx.match modes, a nested grid and a component built on the server."""

import reflex as rx

LAYOUTS = ("cards", "list", "table")
SHAPES = ("circle", "square", "badge")


class WidgetState(rx.State):
    """What the widgets page renders and how."""

    layout: str = "cards"
    shape: str = "circle"
    matrix: rx.Field[list[list[int]]] = rx.field(
        default_factory=lambda: [[1, 2, 3], [4, 5, 6]]
    )
    clicks: rx.Field[int] = rx.field(0)

    @rx.event
    def set_layout(self, value: str | list[str]):
        """Choose how the grid renders, through rx.match.

        Args:
            value: One of ``cards``, ``list`` and ``table``.
        """
        if value in LAYOUTS:
            self.layout = value

    @rx.event
    def next_shape(self):
        """Switch the server-built component to its next shape."""
        self.shape = SHAPES[(SHAPES.index(self.shape) + 1) % len(SHAPES)]

    @rx.event
    def add_row(self):
        """Append a row to the grid, continuing its numbers."""
        start = sum(len(row) for row in self.matrix) + 1
        self.matrix.append(list(range(start, start + 3)))

    @rx.event
    def bump_cell(self, row: int, column: int):
        """Add ten to one cell, editing the nested list in place.

        Args:
            row: The cell's row.
            column: The cell's column.
        """
        self.matrix[row][column] += 10
        self.clicks += 1

    @rx.event
    def reset_grid(self):
        """Start over with two rows."""
        self.matrix = [[1, 2, 3], [4, 5, 6]]
        self.clicks = 0


@rx.dynamic
def shape_badge(state: WidgetState) -> rx.Component:
    """Build a component on the server from the state, with rx.dynamic.

    Args:
        state: The widget state.

    Returns:
        A badge whose component depends on the chosen shape. It carries no
        id: on reflex 0.8.23 an id adds a hook the built component breaks on.
    """
    if state.shape == "circle":
        return rx.avatar(fallback="C", radius="full")
    if state.shape == "square":
        return rx.avatar(fallback="S", radius="none")
    return rx.badge("badge")
