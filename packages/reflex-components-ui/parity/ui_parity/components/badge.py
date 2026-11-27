"""The badge: every variant, size and color, alone and among other things."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, LIGHT, Matrix
from ui_parity.samples import ACCENTS

VARIANTS = ["solid", "soft", "surface", "outline"]
SIZES = ["1", "2", "3"]
RADII = ["none", "small", "medium", "large", "full"]
RESPONSIVE = {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")}


def _badge(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a badge, with what a cell says it holds or is inside of.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``holds`` names the children when they
            are not words alone, and ``inside`` what is around the badge.

    Returns:
        The badge, or what is around it.
    """
    props = dict(props)
    holds = props.pop("holds", None)
    inside = props.pop("inside", None)
    props["custom_attrs"] = {"data-badge": ""}
    if holds == "icon":
        badge = namespace.badge(rx.icon("check", size=12), "Shipped", **props)
    else:
        badge = namespace.badge("In progress", **props)
    if inside == "flex":
        # A badge keeps its height in a row of taller things.
        return namespace.flex(
            namespace.heading("Order 42", size="6"),
            badge,
            namespace.text("since Monday", size="2"),
            spacing="2",
        )
    if inside == "text":
        return namespace.text("The order is ", badge, " and leaves soon.", size="3")
    return badge


MATRIX = Matrix(
    component="badge",
    render=_badge,
    cross={"variant": VARIANTS, "size": SIZES},
    sweep={
        "color_scheme": ACCENTS,
        "radius": RADII,
        "high_contrast": [True],
        "holds": ["icon"],
        "inside": ["flex", "text"],
        "size": RESPONSIVE,
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        {
            "variant": VARIANTS,
            "high_contrast": [False, True],
            "appearance": [LIGHT, DARK],
        },
        {
            "variant": VARIANTS,
            "color_scheme": ["ruby", "gray", "yellow"],
            "high_contrast": [False, True],
            "appearance": [LIGHT, DARK],
        },
        {"radius": RADII, "size": SIZES},
        {"variant": VARIANTS, "holds": ["icon"], "size": SIZES},
        {"variant": VARIANTS, "inside": ["flex", "text"]},
        {"size": RESPONSIVE, "viewport": [520, 800, 1100, 1280]},
    ],
    stage=(320, 100),
    target="[data-badge]",
    crop="stage",
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="badge",
    render=lambda namespace: namespace.box(
        namespace.badge("New", id="badge", title="Added this week"),
        namespace.badge(
            rx.icon("check", size=12),
            "Shipped",
            id="shipped",
            variant="solid",
            color_scheme="green",
        ),
    ),
)


@CONTRACT.step("is a span with its text in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    badge = run.server.element("badge")
    assert (badge.tag, badge.text) == ("span", "New")
    assert badge.attributes["title"] == "Added this week"
    shipped = run.server.element("shipped")
    assert (shipped.tag, shipped.text) == ("span", "Shipped")


@CONTRACT.step("is shown with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    assert run.page.locator("#badge").inner_text() == "New"
    assert run.page.locator("#shipped").is_visible()


@CONTRACT.step("has no role and does not take the focus", on=HYDRATED)
def _role(run: Run) -> None:
    badge = run.page.locator("#badge")
    assert badge.get_attribute("role") is None
    assert badge.evaluate("element => element.tabIndex") == -1
    assert run.page.get_by_text("New", exact=True).get_attribute("id") == "badge"
    run.page.keyboard.press("Tab")
    assert run.page.evaluate("document.activeElement.tagName") == "BODY"
