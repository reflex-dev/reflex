"""Text: sizes, weights, alignment, trim, color and the element it renders."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix
from ui_parity.samples import ACCENTS, PARAGRAPH

def _text(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a paragraph that wraps over several lines.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell, ``nested`` naming what is inside.

    Returns:
        The text.
    """
    props = dict(props)
    nested = props.pop("nested", None)
    if nested == "text":
        return namespace.text(
            "The quick ",
            namespace.text("brown fox", as_="span", weight="bold"),
            " jumps over the lazy dog.",
            **props,
        )
    if nested == "high-contrast":
        return namespace.text(
            "The quick ",
            namespace.text("brown fox", as_="span", high_contrast=True),
            " jumps over the lazy dog.",
            **props,
        )
    if nested in ("em", "strong", "quote", "span"):
        return namespace.text(
            "The quick ",
            getattr(namespace.text, nested)("brown fox jumps"),
            " over the lazy dog, then naps in the sun.",
            **props,
        )
    return namespace.text(PARAGRAPH, **props)


MATRIX = Matrix(
    component="text",
    render=_text,
    cross={
        "size": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
        "weight": ["light", "regular", "medium", "bold"],
    },
    sweep={
        "align": ["left", "center", "right"],
        "trim": ["normal", "start", "end", "both"],
        "as_": ["p", "label", "div", "span", "b", "i", "u", "abbr", "cite", "del",
                "em", "ins", "kbd", "mark", "s", "samp", "sub", "sup"],
        "color_scheme": ACCENTS,
        "high_contrast": [True],
        "nested": ["text", "high-contrast", "em", "strong", "quote", "span"],
        "size": {
            "responsive": rx.breakpoints(initial="1", sm="5", lg="3"),
        },
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        {"color_scheme": ["ruby", "gray"], "high_contrast": [True],
         "appearance": ["light", DARK]},
        {"color_scheme": ["ruby"], "nested": ["text", "high-contrast"]},
        {"trim": ["both", "start"], "size": ["2", "6"]},
        {"nested": ["em", "strong", "quote"], "size": ["1", "5", "9"]},
        {"size": {"responsive": rx.breakpoints(initial="1", sm="5", lg="3")},
         "trim": {"responsive": rx.breakpoints(initial="both", md="normal")},
         "viewport": [520, 800, 1100, 1280]},
    ],
    stage=(260, 200),
)

CONTRACT = Contract(
    component="text",
    render=lambda namespace: namespace.box(
        namespace.text("paragraph", id="text"),
        namespace.text(
            "label", as_="label", id="label", custom_attrs={"htmlFor": "field"}
        ),
        rx.el.input(id="field"),
    ),
)


@CONTRACT.step("is a paragraph in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    text = run.server.element("text")
    assert (text.tag, text.text) == ("p", "paragraph")
    assert run.server.element("label").tag == "label"


@CONTRACT.step("is shown with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    text = run.page.locator("#text")
    assert text.is_visible()
    assert text.inner_text() == "paragraph"


@CONTRACT.step("as a label, a click moves the focus to its field", on=HYDRATED)
def _label(run: Run) -> None:
    run.page.locator("#label").click()
    assert run.page.evaluate("document.activeElement.id") == "field"
