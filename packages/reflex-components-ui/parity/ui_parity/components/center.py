"""The center: a flex container with its content in the middle."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix
from ui_parity.samples import tiles


def _center(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a center taller than its content.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell.

    Returns:
        The center.
    """
    return namespace.center(*tiles(("quick", "brown", "fox")), **props)


MATRIX = Matrix(
    component="center",
    render=_center,
    base={"style": {"height": "100px"}},
    sweep={
        "direction": ["row", "column"],
        "spacing": ["2", "5"],
        # Centering wins over both, as it does in rx.
        "align": ["start", "end"],
        "justify": ["start", "between"],
        "wrap": ["wrap"],
        "appearance": [DARK],
        "viewport": [520],
    },
    stage=(240, 140),
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="center",
    render=lambda namespace: namespace.center(
        namespace.box("content", id="content"),
        id="center",
        style={"height": "200px"},
    ),
)


@CONTRACT.step("is a div in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    center = run.server.element("center")
    assert (center.tag, center.text) == ("div", "content")


@CONTRACT.step("is shown with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    assert run.page.locator("#content").is_visible()


@CONTRACT.step("holds its content in the middle after hydration", on=HYDRATED)
def _hydrated(run: Run) -> None:
    center = run.page.locator("#center").bounding_box()
    content = run.page.locator("#content").bounding_box()
    assert center is not None
    assert content is not None
    for start, length in (("x", "width"), ("y", "height")):
        before = content[start] - center[start]
        after = center[start] + center[length] - content[start] - content[length]
        assert abs(before - after) <= 1
