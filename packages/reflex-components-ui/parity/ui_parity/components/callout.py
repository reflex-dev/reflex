"""The callout: a message with or without an icon, in each variant and size."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, LIGHT, Matrix
from ui_parity.samples import ACCENTS, PARAGRAPH

VARIANTS = ["soft", "surface", "outline"]
SIZES = ["1", "2", "3"]
RESPONSIVE = rx.breakpoints(initial="1", sm="3", lg="2")


def _callout(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a callout, from its text or from its parts.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``holds`` names what a callout made of
            its parts holds, and ``text`` the text of the other kind.

    Returns:
        The callout.
    """
    props = dict(props)
    holds = props.pop("holds", None)
    text = props.pop("text", "Access denied. Ask an admin for it.")
    if holds is None:
        return namespace.callout(text, **props)
    props.pop("icon", None)
    children = [
        namespace.callout.icon(rx.icon("info", size=16)),
        namespace.callout.text(text),
    ]
    if holds == "more":
        # What is neither the icon nor the text is in the column of the text.
        children.extend((
            rx.el.div("Retry in a minute.", style={"font_size": "12px"}),
            namespace.callout.text("And a second paragraph."),
        ))
    if holds == "text":
        children = children[1:]
    return namespace.callout.root(*children, **props)


MATRIX = Matrix(
    component="callout",
    render=_callout,
    base={"icon": "info"},
    cross={"variant": VARIANTS, "size": SIZES, "icon": ["info", None]},
    sweep={
        "color_scheme": ACCENTS,
        "high_contrast": [True],
        "holds": ["parts", "more", "text"],
        "text": {"long": PARAGRAPH},
        "size": {"responsive": RESPONSIVE},
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
        },
        {"holds": ["more"], "size": SIZES, "variant": VARIANTS},
        {"text": {"long": PARAGRAPH}, "size": SIZES, "icon": ["info", None]},
        {"size": {"responsive": RESPONSIVE}, "viewport": [520, 800, 1100, 1280]},
    ],
    stage=(320, 200),
    parts={"text": "p"},
    # Not held to zero, for the icon: at a threshold of zero 100 of the 101
    # cells are equal pixel for pixel, and in the base cell at a width of
    # 520 the edge of the icon is anti-aliased otherwise (one pixel beyond
    # anti-aliasing). The same callout at the other widths is equal.
    tolerance=0.002,
)

CONTRACT = Contract(
    component="callout",
    render=lambda namespace: namespace.box(
        namespace.callout("Saved.", icon="check", id="saved"),
        namespace.callout.root(
            namespace.callout.icon(rx.icon("info"), id="icon"),
            namespace.callout.text("Read this.", id="text"),
            id="root",
        ),
    ),
)


@CONTRACT.step(
    "is a div around an icon and a paragraph in the server render", on=SERVER
)
def _server_render(run: Run) -> None:
    saved = run.server.element("saved")
    assert (saved.tag, saved.text) == ("div", "Saved.")
    assert run.server.element("icon").tag == "div"
    text = run.server.element("text")
    assert (text.tag, text.text) == ("p", "Read this.")


@CONTRACT.step(
    "shows its icon beside its text with JavaScript disabled", on=NO_JAVASCRIPT
)
def _without_javascript(run: Run) -> None:
    _icon_is_beside_the_text(run)


@CONTRACT.step("shows its icon beside its text after hydration", on=HYDRATED)
def _hydrated(run: Run) -> None:
    _icon_is_beside_the_text(run)
    assert run.page.get_by_role("paragraph").count() == 2


def _icon_is_beside_the_text(run: Run) -> None:
    """Check that the icon is left of the text, on its first line.

    Args:
        run: The run of the step.
    """
    icon = run.page.locator("#icon").bounding_box()
    text = run.page.locator("#text").bounding_box()
    assert icon is not None
    assert text is not None
    assert icon["x"] + icon["width"] < text["x"]
    assert (icon["y"], icon["height"]) == (text["y"], text["height"])
