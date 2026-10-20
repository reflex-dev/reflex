"""The widgets page: rx.match, nested rx.foreach, rx.memo, rx.ComponentState, rx.dynamic and a custom component."""

import reflex as rx

from playground.components.widgets import LiveClock, Stepper, stat_card
from playground.layout import layout
from playground.states.widgets import LAYOUTS, WidgetState, shape_badge


def cell(value: rx.Var[int], row: rx.Var[int], column: rx.Var[int]) -> rx.Component:
    """Render one cell of the grid; clicking it adds ten.

    Args:
        value: The cell's number.
        row: Its row.
        column: Its column.

    Returns:
        A clickable cell.
    """
    return rx.button(
        value,
        on_click=WidgetState.bump_cell(row, column),
        variant="surface",
        class_name="min-w-12",
    )


def grid_row(row: rx.Var[list[int]], index: rx.Var[int]) -> rx.Component:
    """Render one row of the grid, a foreach inside a foreach.

    Args:
        row: The row's numbers.
        index: The row's index.

    Returns:
        The row's cells.
    """
    return rx.hstack(rx.foreach(row, lambda value, column: cell(value, index, column)))


def matrix_view() -> rx.Component | rx.Var:
    """Render the grid in the chosen layout, through rx.match.

    Returns:
        Cards, a list or a table of the grid.
    """
    return rx.match(
        WidgetState.layout,
        (
            "list",
            rx.unordered_list(
                rx.foreach(
                    WidgetState.matrix,
                    lambda row: rx.list_item(row.to_string()),
                )
            ),
        ),
        (
            "table",
            rx.table.root(
                rx.table.body(
                    rx.foreach(
                        WidgetState.matrix,
                        lambda row: rx.table.row(
                            rx.foreach(row, lambda value: rx.table.cell(value))
                        ),
                    )
                )
            ),
        ),
        rx.vstack(rx.foreach(WidgetState.matrix, grid_row)),
    )


def widgets() -> rx.Component:
    """Render the widgets page.

    Returns:
        Stat cards, the grid, two steppers, the server-built badge and the clock.
    """
    return layout(
        rx.vstack(
            rx.heading("Widgets"),
            rx.hstack(
                stat_card(label="Layout", value=WidgetState.layout),
                stat_card(label="Clicks", value=WidgetState.clicks.to_string()),
                stat_card(label="Rows", value=WidgetState.matrix.length().to_string()),
                spacing="3",
                wrap="wrap",
                id="widgets-stats",
            ),
            rx.hstack(
                rx.segmented_control.root(
                    *[rx.segmented_control.item(name, value=name) for name in LAYOUTS],
                    value=WidgetState.layout,
                    on_change=WidgetState.set_layout,
                    id="widgets-layout",
                ),
                rx.button(
                    "Add row", on_click=WidgetState.add_row, id="widgets-add-row"
                ),
                rx.button(
                    "Reset",
                    on_click=WidgetState.reset_grid,
                    variant="soft",
                    id="widgets-reset",
                ),
                spacing="2",
            ),
            rx.box(matrix_view(), id="widgets-matrix"),
            rx.heading("Component state", size="3"),
            Stepper.create(label="First", prefix="widgets-stepper-a"),
            Stepper.create(label="Second", prefix="widgets-stepper-b"),
            rx.heading("Built on the server", size="3"),
            rx.hstack(
                rx.box(shape_badge(), id="widgets-dynamic-shape"),
                rx.button(
                    "Next shape",
                    on_click=WidgetState.next_shape,
                    id="widgets-next-shape",
                ),
                align="center",
            ),
            rx.heading("Custom component", size="3"),
            rx.text("Local time: ", LiveClock.create(id="widgets-clock")),
            width="100%",
        )
    )
