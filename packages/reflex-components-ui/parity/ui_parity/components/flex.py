"""The flex container: direction, alignment, wrapping and gaps."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix
from ui_parity.samples import tiles


def _flex(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a flex container whose children do not fit on one line.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell.

    Returns:
        The container.
    """
    return namespace.flex(
*tiles(), **props
    )


MATRIX = Matrix(
    component="flex",
    render=_flex,
    cross={
        "direction": ["row", "column", "row-reverse", "column-reverse"],
        "wrap": ["nowrap", "wrap", "wrap-reverse"],
    },
    sweep={
        "align": ["start", "center", "end", "baseline", "stretch"],
        "justify": ["start", "center", "end", "between"],
        "spacing": ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
        "style": {"sized": {"height": "80px", "padding": "4px"}},
        "appearance": [DARK],
    },
    groups=[
        {"wrap": ["wrap"], "spacing": ["2", "5"], "justify": ["between", "end"]},
        {"style": {"sized": {"height": "80px"}}, "align": ["center", "end"]},
        {
            "direction": {
                "responsive": rx.breakpoints(initial="column", sm="row", lg="column")
            },
            "spacing": {"responsive": rx.breakpoints(initial="1", xs="4", md="2")},
            "viewport": [400, 600, 800, 1100, 1280],
        },
    ],
    stage=(240, 160),
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="flex",
    render=lambda namespace: namespace.flex(
        namespace.box("one"), namespace.box("two"), id="flex", spacing="2"
    ),
)


@CONTRACT.step("is a div in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    flex = run.server.element("flex")
    assert (flex.tag, flex.text) == ("div", "onetwo")


@CONTRACT.step("is shown with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    flex = run.page.locator("#flex")
    assert flex.is_visible()
    assert flex.evaluate("element => getComputedStyle(element).display") == "flex"


@CONTRACT.step("lays its children out in a row after hydration", on=HYDRATED)
def _hydrated(run: Run) -> None:
    boxes = run.page.locator("#flex > div")
    first, second = boxes.nth(0).bounding_box(), boxes.nth(1).bounding_box()
    assert first is not None
    assert second is not None
    assert first["y"] == second["y"]
    assert second["x"] > first["x"]
