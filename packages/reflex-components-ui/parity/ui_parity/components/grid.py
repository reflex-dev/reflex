"""The grid container: tracks, flow, alignment and gaps."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix
from ui_parity.samples import tiles


def _grid(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a grid of more children than one row holds.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell.

    Returns:
        The grid.
    """
    return namespace.grid(*tiles(), **props)


MATRIX = Matrix(
    component="grid",
    render=_grid,
    cross={
        "columns": ["1", "2", "3", "4"],
        "spacing": ["0", "2", "5"],
    },
    sweep={
        "columns": {"lengths": "60px 1fr", "repeat": "repeat(3, 40px)"},
        "rows": ["2", "3", "repeat(4, 20px)"],
        "flow": ["row", "column", "dense", "row-dense", "column-dense"],
        "align": ["start", "center", "end", "baseline", "stretch"],
        "justify": ["start", "center", "end", "between"],
        "spacing": ["1", "3", "4", "6", "7", "8", "9"],
        "spacing_x": ["1", "4", "9"],
        "spacing_y": ["1", "4", "9"],
        "style": {"sized": {"height": "140px", "padding": "4px"}},
        "appearance": [DARK],
    },
    groups=[
        {"rows": ["3"], "flow": ["column", "column-dense"], "spacing": ["2"]},
        {"columns": ["3"], "spacing_x": ["4"], "spacing_y": ["1"]},
        {
            "columns": {"sized": "repeat(3, 40px)"},
            "justify": ["center", "end", "between"],
        },
        {
            "columns": {
                "responsive": rx.breakpoints(initial="1", xs="2", md="4", lg="3")
            },
            "spacing": {"responsive": rx.breakpoints(initial="1", sm="4")},
            "viewport": [400, 600, 800, 1100, 1280],
        },
    ],
    stage=(260, 180),
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="grid",
    render=lambda namespace: namespace.grid(
        namespace.box("one"), namespace.box("two"), id="grid", columns="2"
    ),
)


@CONTRACT.step("is a div in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    grid = run.server.element("grid")
    assert (grid.tag, grid.text) == ("div", "onetwo")


@CONTRACT.step("is a grid with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    grid = run.page.locator("#grid")
    assert grid.is_visible()
    assert grid.evaluate("element => getComputedStyle(element).display") == "grid"


@CONTRACT.step("lays its children out in two columns after hydration", on=HYDRATED)
def _hydrated(run: Run) -> None:
    boxes = run.page.locator("#grid > div")
    first, second = boxes.nth(0).bounding_box(), boxes.nth(1).bounding_box()
    assert first is not None
    assert second is not None
    assert first["y"] == second["y"]
    assert first["width"] == second["width"]
    assert second["x"] == first["x"] + first["width"]
