"""The storage page: a cookie, a localStorage entry and a sessionStorage entry."""

import reflex as rx

from playground.layout import layout
from playground.states.storage import StorageState


def storage_row(
    kind: str, value: rx.Var[str] | str, control: rx.Component
) -> rx.Component:
    """Render one stored value and its control.

    Args:
        kind: Where the browser keeps it.
        value: The value.
        control: What changes it.

    Returns:
        A table row.
    """
    return rx.table.row(
        rx.table.row_header_cell(kind),
        rx.table.cell(rx.code(value)),
        rx.table.cell(control),
    )


def storage() -> rx.Component:
    """Render the storage page.

    Returns:
        The three values and their controls.
    """
    return layout(
        rx.vstack(
            rx.heading("Client storage"),
            rx.text(
                "The browser keeps these values and sends them to the server when a "
                "page loads, so they survive a restart of the backend."
            ),
            rx.table.root(
                rx.table.body(
                    storage_row(
                        "Cookie",
                        StorageState.note,
                        rx.input(
                            placeholder="a note",
                            on_blur=StorageState.set_note,
                            id="storage-cookie",
                        ),
                    ),
                    storage_row(
                        "localStorage",
                        StorageState.visits,
                        rx.button(
                            "Count a visit",
                            on_click=StorageState.count_visit,
                            id="storage-local",
                        ),
                    ),
                    storage_row(
                        "sessionStorage",
                        StorageState.draft,
                        rx.input(
                            placeholder="a draft",
                            on_blur=StorageState.set_draft,
                            id="storage-session",
                        ),
                    ),
                ),
                id="storage-values",
            ),
            rx.button(
                "Forget all",
                on_click=StorageState.forget,
                variant="soft",
                color_scheme="red",
                id="storage-forget",
            ),
        )
    )
