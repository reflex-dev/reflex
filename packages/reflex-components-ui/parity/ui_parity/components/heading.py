"""The heading: sizes, weights, alignment, trim, color and its level."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix
from ui_parity.samples import ACCENTS

TITLE = "The quick brown fox jumps over the lazy dog"


def _heading(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a heading that wraps over several lines.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell, ``nested`` naming what is inside.

    Returns:
        The heading.
    """
    props = dict(props)
    nested = props.pop("nested", None)
    if nested == "text":
        return namespace.heading(
            "The quick ",
            namespace.text("brown fox", as_="span", weight="regular"),
            " jumps over the lazy dog",
            **props,
        )
    if nested == "code":
        return namespace.heading(
            "The quick ", namespace.code("brown fox"), " jumps over", **props
        )
    if nested == "high-contrast":
        return namespace.heading(
            "The quick ",
            namespace.text("brown fox", as_="span", high_contrast=True),
            " jumps over the lazy dog",
            **props,
        )
    return namespace.heading(TITLE, **props)


RESPONSIVE = rx.breakpoints(initial="2", sm="8", lg="4")

MATRIX = Matrix(
    component="heading",
    render=_heading,
    cross={
        "size": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
        "weight": ["light", "regular", "medium", "bold"],
    },
    sweep={
        "align": ["left", "center", "right"],
        "trim": ["normal", "start", "end", "both"],
        "as_": ["h1", "h2", "h3", "h4", "h5", "h6", "div"],
        "color_scheme": ACCENTS,
        "high_contrast": [True],
        "nested": ["text", "code", "high-contrast"],
        "size": {"responsive": RESPONSIVE},
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        {
            "color_scheme": ["ruby", "gray"],
            "high_contrast": [True],
            "appearance": ["light", DARK],
        },
        {"color_scheme": ["ruby"], "nested": ["text", "code", "high-contrast"]},
        {"trim": ["both", "start", "end"], "size": ["2", "4", "8"]},
        {"nested": ["text", "code"], "size": ["2", "8"]},
        {
            "size": {"responsive": RESPONSIVE},
            "trim": {"responsive": rx.breakpoints(initial="both", md="normal")},
            "align": {"responsive": rx.breakpoints(initial="center", sm="right")},
            "viewport": [520, 800, 1100, 1280],
        },
    ],
    stage=(300, 240),
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="heading",
    render=lambda namespace: namespace.box(
        namespace.heading("Title", id="title"),
        namespace.heading("Subtitle", as_="h2", id="subtitle"),
    ),
)


@CONTRACT.step("is a heading of its level in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    title = run.server.element("title")
    assert (title.tag, title.text) == ("h1", "Title")
    assert run.server.element("subtitle").tag == "h2"


@CONTRACT.step("is shown with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    assert run.page.locator("#title").inner_text() == "Title"


@CONTRACT.step("has the role of a heading and its level", on=HYDRATED)
def _roles(run: Run) -> None:
    assert run.page.get_by_role("heading", level=1).get_attribute("id") == "title"
    assert run.page.get_by_role("heading", level=2).get_attribute("id") == "subtitle"
