"""Compare a bound deletion event with Glide's default deletion behavior."""

import importlib.metadata
import json
import os
from pathlib import Path
from typing import Any

import reflex as rx

assert Path(rx.__file__).is_relative_to(
    Path(os.environ["SB"]) / "envs" / os.environ["QA_ENV"]
), rx.__file__


class State(rx.State):
    """Record the callback payloads and text-cell values."""

    rows: list[list[str]] = [["alpha"], ["beta"]]
    edits: int = 0
    clicked: str = ""
    deleted: str = ""

    @rx.event
    def click(self, pos: tuple[int, int]):
        """Record which cell the browser selected.

        Args:
            pos: Selected column and row.
        """
        self.clicked = json.dumps(pos)

    @rx.event
    def edit(self, pos: tuple[int, int], cell: dict[str, Any]):
        """Apply an ordinary text-cell edit.

        Args:
            pos: Edited column and row.
            cell: Glide cell payload.
        """
        self.rows[pos[1]][pos[0]] = cell["data"]
        self.edits += 1

    @rx.event
    def delete(self, selection: dict[str, Any]):
        """Record the selection without changing deletion behavior.

        Args:
            selection: Glide selection emitted by on_delete.
        """
        self.deleted = json.dumps(selection, sort_keys=True)


def scenario(bound: bool) -> rx.Component:
    """Build two pages differing only in whether on_delete is bound.

    Args:
        bound: Whether to bind a normal backend event handler.

    Returns:
        The deletion fixture page.
    """
    return rx.vstack(
        rx.heading("Bound on_delete" if bound else "Default deletion"),
        rx.text(f"reflex={importlib.metadata.version('reflex')}", id="versions"),
        rx.text(State.clicked, id="clicked"),
        rx.text(State.deleted, id="deleted"),
        rx.text(State.edits, id="edits"),
        rx.text(State.rows.to_string(), id="rows"),
        rx.box(
            rx.data_editor(
                columns=[{"title": "Name", "type": "str", "width": 180}],
                data=State.rows,
                row_markers="number",
                row_height=40,
                header_height=36,
                on_cell_clicked=State.click,
                on_cell_edited=State.edit,
                **({"on_delete": State.delete} if bound else {}),
                width="260px",
                height="170px",
            ),
            id="grid",
            width="260px",
            height="170px",
        ),
        padding="20px",
    )


def control() -> rx.Component:
    """Return the default-deletion control.

    Returns:
        The page without an on_delete handler.
    """
    return scenario(False)


def bound() -> rx.Component:
    """Return the page with the deletion callback.

    Returns:
        The page with an on_delete handler.
    """
    return scenario(True)


def form_scenario(with_grid: bool) -> rx.Component:
    """Compare Radix form controls with and without a co-located data editor.

    Args:
        with_grid: Whether the page includes a data editor.

    Returns:
        A form with three controls and an optional static grid.
    """
    return rx.vstack(
        rx.heading("Form with grid" if with_grid else "Form without grid"),
        rx.form(
            rx.checkbox("Checkbox", id="checkbox"),
            rx.switch(id="switch"),
            rx.radio_group(["a", "b"], id="radio"),
            *(
                [
                    rx.data_editor(
                        columns=[{"title": "Value", "type": "str"}],
                        data=[["literal"]],
                        width="200px",
                        height="120px",
                    )
                ]
                if with_grid
                else []
            ),
        ),
        padding="20px",
    )


def form_grid() -> rx.Component:
    """Return the form with a data editor.

    Returns:
        The candidate form interaction page.
    """
    return form_scenario(True)


def form_only() -> rx.Component:
    """Return the form without a data editor.

    Returns:
        The form-control negative control.
    """
    return form_scenario(False)


app = rx.App()
app.add_page(control, route="/")
app.add_page(bound, route="/bound")
app.add_page(form_grid, route="/form-grid")
app.add_page(form_only, route="/form-only")
