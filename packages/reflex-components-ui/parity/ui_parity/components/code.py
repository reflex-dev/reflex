"""Inline code: variants, sizes, color, and code inside text and links."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, HOVER, Matrix
from ui_parity.samples import ACCENTS


def _code(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create inline code, alone or inside something that changes its look.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``inside`` names what is around the
            code, at the size ``around`` gives.

    Returns:
        The code, or what is around it.
    """
    props = dict(props)
    inside = props.pop("inside", None)
    around = props.pop("around", "3")
    code = namespace.code("uv run reflex", **props)
    if inside == "text":
        return namespace.text("Run ", code, " to start the app.", size=around)
    if inside == "heading":
        return namespace.heading("Run ", code, " first", size=around)
    if inside == "link":
        return namespace.text(
            "See ", namespace.link(code, href="/docs"), " for more.", size=around
        )
    return code


MATRIX = Matrix(
    component="code",
    render=_code,
    cross={
        "variant": ["soft", "solid", "outline", "ghost"],
        "size": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
    },
    sweep={
        # Radix Themes has neither for code: both look like soft.
        "variant": ["classic", "surface"],
        "weight": ["light", "regular", "medium", "bold"],
        "color_scheme": ACCENTS,
        "high_contrast": [True],
        "inside": ["text", "heading", "link"],
        "size": {"responsive": rx.breakpoints(initial="1", sm="6", lg="3")},
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        {
            "variant": ["soft", "solid", "outline", "ghost"],
            "color_scheme": ["ruby", "gray", "yellow"],
            "high_contrast": [False, True],
            "appearance": ["light", DARK],
        },
        {
            "variant": ["soft", "solid", "outline", "ghost"],
            "high_contrast": [True],
        },
        {
            "variant": ["soft", "solid", "outline", "ghost"],
            "inside": ["text", "heading", "link"],
            "around": ["2", "6"],
        },
        {
            "variant": ["soft", "solid", "outline", "ghost"],
            "inside": [None, "link"],
            "state": [HOVER],
        },
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="6", lg="3")},
            "viewport": [520, 800, 1280],
        },
    ],
    stage=(300, 120),
    target="code",
    crop="stage",
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="code",
    render=lambda namespace: namespace.code("uv sync", id="code"),
)


@CONTRACT.step("is a code element in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    code = run.server.element("code")
    assert (code.tag, code.text) == ("code", "uv sync")


@CONTRACT.step("is shown with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    assert run.page.locator("#code").inner_text() == "uv sync"


@CONTRACT.step("has the role of code after hydration", on=HYDRATED)
def _role(run: Run) -> None:
    assert run.page.get_by_role("code").get_attribute("id") == "code"
