"""The horizontal stack: a row with a gap between its children."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix
from ui_parity.samples import tiles


def _hstack(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a stack of more children than one line holds.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell.

    Returns:
        The stack.
    """
    return namespace.hstack(*tiles(), **props)


MATRIX = Matrix(
    component="hstack",
    render=_hstack,
    sweep={
        "spacing": ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
        "align": ["start", "center", "end", "baseline", "stretch"],
        "justify": ["start", "center", "end", "between"],
        "direction": ["row", "column", "row-reverse", "column-reverse"],
        "wrap": ["nowrap", "wrap", "wrap-reverse"],
        "class_name": ["mine"],
        "style": {"sized": {"height": "120px", "width": "100%"}},
        "appearance": [DARK],
    },
    groups=[
        {"wrap": ["wrap"], "spacing": ["1", "4"], "align": ["center", "end"]},
        {
            "style": {"sized": {"height": "120px", "width": "100%"}},
            "justify": ["center", "between"],
            "align": ["center", "stretch"],
        },
        {
            "direction": {
                "responsive": rx.breakpoints(initial="column", sm="row", lg="column")
            },
            "spacing": {"responsive": rx.breakpoints(initial="1", xs="5", md="2")},
            "align": {"responsive": rx.breakpoints(initial="end", md="center")},
            "viewport": [400, 600, 800, 1100, 1280],
        },
    ],
    stage=(240, 200),
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="hstack",
    render=lambda namespace: namespace.hstack(
        namespace.box("one"), namespace.box("two"), id="stack"
    ),
)


@CONTRACT.step("is a div with the class of a stack in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    stack = run.server.element("stack")
    assert (stack.tag, stack.text) == ("div", "onetwo")
    assert "rx-Stack" in (stack.attributes["class"] or "").split()


@CONTRACT.step("is shown with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    assert run.page.locator("#stack").is_visible()


@CONTRACT.step("lays its children out in a row, a gap apart", on=HYDRATED)
def _hydrated(run: Run) -> None:
    boxes = run.page.locator("#stack > div")
    first, second = boxes.nth(0).bounding_box(), boxes.nth(1).bounding_box()
    assert first is not None
    assert second is not None
    # The default spacing is the third step of the space scale: 12px.
    assert second["y"] == first["y"]
    assert second["x"] == first["x"] + first["width"] + 12
