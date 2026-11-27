"""The container: the width it bounds its content to."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix
from ui_parity.samples import PARAGRAPH


def _container(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a container whose content shows the width it is given.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell.

    Returns:
        The container.
    """
    return namespace.container(
        rx.el.div(PARAGRAPH, style={"border": "1px solid currentColor"}),
        **props,
    )


MATRIX = Matrix(
    component="container",
    render=_container,
    sweep={
        "size": ["1", "2", "3", "4"],
        "padding": ["0px", "32px"],
        "style": {"background": {"background_color": "rgba(128, 128, 128, 0.2)"}},
        "appearance": [DARK],
    },
    groups=[
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="2", lg="4")},
            "viewport": [520, 800, 1280],
        },
    ],
    # Wider than the widest container.
    stage=(1232, 96),
    parts={"inner": ":scope > div > div"},
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="container",
    render=lambda namespace: namespace.container(
        namespace.box("content", id="content"), id="container", size="1"
    ),
)


@CONTRACT.step("wraps its content in a div in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    container = run.server.element("container")
    assert (container.tag, container.text) == ("div", "content")


@CONTRACT.step("is shown with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    assert run.page.locator("#content").is_visible()


@CONTRACT.step("bounds and centers its content after hydration", on=HYDRATED)
def _hydrated(run: Run) -> None:
    container = run.page.locator("#container").bounding_box()
    inner = run.page.locator("#container > div").bounding_box()
    assert container is not None
    assert inner is not None
    assert inner["width"] == 448
    assert inner["x"] - container["x"] == (container["width"] - 448) / 2
