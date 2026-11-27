"""The block quotation: text with a rule beside it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix
from ui_parity.samples import ACCENTS, PARAGRAPH


def _blockquote(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a quotation that wraps over several lines.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell.

    Returns:
        The quotation.
    """
    return namespace.blockquote(PARAGRAPH, **props)


MATRIX = Matrix(
    component="blockquote",
    render=_blockquote,
    cross={
        "size": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
        "weight": ["light", "regular", "medium", "bold"],
    },
    sweep={
        "color_scheme": ACCENTS,
        "high_contrast": [True],
        "size": {"responsive": rx.breakpoints(initial="1", sm="5", lg="3")},
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        {
            "color_scheme": ["ruby", "gray"],
            "high_contrast": [True],
            "appearance": ["light", DARK],
        },
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="5", lg="3")},
            "viewport": [520, 800, 1280],
        },
    ],
    stage=(300, 260),
)

CONTRACT = Contract(
    component="blockquote",
    render=lambda namespace: namespace.blockquote(
        "Stay hungry", id="quote", cite="https://example.com/speech"
    ),
)


@CONTRACT.step("is a blockquote with its source in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    quote = run.server.element("quote")
    assert (quote.tag, quote.text) == ("blockquote", "Stay hungry")
    assert quote.attributes["cite"] == "https://example.com/speech"


@CONTRACT.step("is shown with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    assert run.page.locator("#quote").inner_text() == "Stay hungry"


@CONTRACT.step("has the role of a blockquote after hydration", on=HYDRATED)
def _role(run: Run) -> None:
    assert run.page.get_by_role("blockquote").get_attribute("id") == "quote"
