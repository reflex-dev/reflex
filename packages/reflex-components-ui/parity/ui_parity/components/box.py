"""The box: a div with no look of its own."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, FOCUS_VISIBLE, HOVER, Matrix


def _box(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a box with a line of text.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell.

    Returns:
        The box.
    """
    return namespace.box("The quick brown fox", **props)


MATRIX = Matrix(
    component="box",
    render=_box,
    sweep={
        "style": {
            "padding": {"padding": "12px"},
            "border": {"border": "1px solid currentColor", "borderRadius": "6px"},
        },
        # A div takes the keyboard's focus only when asked to.
        "custom_attrs": {"focusable": {"tabIndex": 0}},
        "appearance": [DARK],
        "state": [HOVER],
        "viewport": [520],
    },
    groups=[
        {"custom_attrs": {"focusable": {"tabIndex": 0}}, "state": [FOCUS_VISIBLE]},
    ],
    # Two divs of one stylesheet: nothing may differ, not even by a shade.
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="box",
    render=lambda namespace: namespace.box("content", id="box"),
)


@CONTRACT.step("is a div in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    box = run.server.element("box")
    assert (box.tag, box.text) == ("div", "content")


@CONTRACT.step("is shown with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    box = run.page.locator("#box")
    assert box.is_visible()
    assert box.inner_text() == "content"


@CONTRACT.step("keeps its content after hydration", on=HYDRATED)
def _hydrated(run: Run) -> None:
    assert run.page.locator("#box").inner_text() == "content"
