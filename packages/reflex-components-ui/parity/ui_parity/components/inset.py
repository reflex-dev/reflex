"""The inset: content that reaches the edges of the card around it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix


def _inset(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create an inset inside a card, which says how far its edges are.

    The card is the Radix one for both systems: it sets the custom properties
    an inset reads, and rx.ui has no card yet.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell, ``card`` holding those of the card.

    Returns:
        The card.
    """
    props = dict(props)
    card = props.pop("card", {})
    return rx.card(
        namespace.inset(
            rx.el.div(
                "The quick brown fox",
                style={"background_color": "rgba(128, 128, 128, 0.4)"},
            ),
            custom_attrs={"data-inset": ""},
            **props,
        ),
        rx.el.div("jumps over the lazy dog"),
        **card,
    )


SIDES = ["x", "y", "top", "bottom", "right", "left"]

MATRIX = Matrix(
    component="inset",
    render=_inset,
    cross={
        "side": SIDES,
        "clip": ["border-box", "padding-box"],
    },
    sweep={
        "clip": ["border-box", "padding-box"],
        "p": ["current", "0"],
        "px": ["current", "0"],
        "py": ["current", "0"],
        "pt": ["current", "0"],
        "pr": ["current", "0"],
        "pb": ["current", "0"],
        "pl": ["current", "0"],
        "card": {
            "size-1": {"size": "1"},
            "size-3": {"size": "3"},
            "classic": {"variant": "classic"},
            "ghost": {"variant": "ghost"},
        },
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        {"side": ["top", "x"], "p": ["current"], "clip": ["padding-box"]},
        {
            "side": {"responsive": rx.breakpoints(initial="top", sm="x", lg="bottom")},
            "clip": {
                "responsive": rx.breakpoints(initial="padding-box", md="border-box")
            },
            "p": {"responsive": rx.breakpoints(initial="current", sm="0")},
            "viewport": [520, 800, 1100, 1280],
        },
    ],
    stage=(260, 140),
    target="[data-inset]",
    crop="stage",
    # Not held to zero, as the other layouts are: the card around the inset
    # is the same Radix card in both frames, and the browser dithers its
    # rounded corners and its shadow by position.
)

CONTRACT = Contract(
    component="inset",
    render=lambda namespace: rx.card(
        namespace.inset(namespace.box("content"), id="inset", side="top"),
        id="card",
    ),
)


@CONTRACT.step("is a div in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    inset = run.server.element("inset")
    assert (inset.tag, inset.text) == ("div", "content")


@CONTRACT.step("reaches the edges of the card with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    _reaches_the_edges(run)


@CONTRACT.step("reaches the edges of the card after hydration", on=HYDRATED)
def _hydrated(run: Run) -> None:
    _reaches_the_edges(run)


def _reaches_the_edges(run: Run) -> None:
    """Check that the inset covers the padding of the card on three sides.

    Args:
        run: The run of the step.
    """
    card = run.page.locator("#card").bounding_box()
    inset = run.page.locator("#inset").bounding_box()
    assert card is not None
    assert inset is not None
    # All but the border of the card, which is one pixel.
    assert (inset["x"], inset["y"], inset["width"]) == (
        card["x"] + 1,
        card["y"] + 1,
        card["width"] - 2,
    )
