"""The grids page: the same rows in a gridjs table and in the glide data editor."""

import reflex as rx

from playground.layout import layout
from playground.states.grids import EDITOR_COLUMNS, GRID_COLUMNS, GridState


def grids() -> rx.Component:
    """Render the grids page.

    Returns:
        The data table and the data editor.
    """
    return layout(
        rx.vstack(
            rx.heading("Grids"),
            rx.text("Edits: ", GridState.edits, id="grids-edits"),
            rx.box(
                rx.data_table(
                    data=GridState.rows,
                    columns=list(GRID_COLUMNS),
                    search=True,
                    sort=True,
                    pagination=True,
                ),
                id="grids-table",
                width="100%",
            ),
            rx.box(
                rx.data_editor(
                    columns=EDITOR_COLUMNS,
                    data=GridState.rows,
                    on_cell_edited=GridState.edit_cell,  # pyright: ignore[reportArgumentType]
                    height="20rem",
                ),
                id="grids-editor",
                width="100%",
            ),
            rx.button(
                "Undo edits",
                on_click=GridState.reset_rows,
                variant="soft",
                id="grids-reset",
            ),
            width="100%",
        )
    )
