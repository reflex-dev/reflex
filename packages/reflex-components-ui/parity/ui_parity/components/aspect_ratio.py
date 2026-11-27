"""The aspect ratio: a box whose height follows its width."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix


def _aspect_ratio(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a box of a ratio whose content fills it.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell.

    Returns:
        The box.
    """
    return namespace.aspect_ratio(
        rx.el.div(
            "16:9",
            style={
                "width": "100%",
                "height": "100%",
                "background_color": "rgba(128, 128, 128, 0.4)",
            },
        ),
        **props,
    )


MATRIX = Matrix(
    component="aspect_ratio",
    render=_aspect_ratio,
    sweep={
        "ratio": {
            "square": 1,
            "wide": 16 / 9,
            "classic": 4 / 3,
            "tall": 0.75,
            "whole": 2,
        },
        "style": {"rounded": {"border_radius": "12px", "overflow": "hidden"}},
        "appearance": [DARK],
        "viewport": [520],
    },
    stage=(232, 320),
    target=":scope > div > div",
    crop="stage",
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="aspect_ratio",
    render=lambda namespace: namespace.box(
        namespace.aspect_ratio(namespace.box("content"), ratio=2, id="ratio"),
        style={"width": "300px"},
    ),
)


@CONTRACT.step("is a div inside the frame that sizes it", on=SERVER)
def _server_render(run: Run) -> None:
    ratio = run.server.element("ratio")
    assert (ratio.tag, ratio.text) == ("div", "content")


@CONTRACT.step("keeps its ratio with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    _keeps_its_ratio(run)


@CONTRACT.step("keeps its ratio after hydration", on=HYDRATED)
def _hydrated(run: Run) -> None:
    _keeps_its_ratio(run)


def _keeps_its_ratio(run: Run) -> None:
    """Check that the box is twice as wide as it is high.

    Args:
        run: The run of the step.
    """
    box = run.page.locator("#ratio").bounding_box()
    assert box is not None
    assert (box["width"], box["height"]) == (300, 150)
