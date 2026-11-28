"""The key of a keyboard, which text names: ``text.kbd`` in both namespaces."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix


def _kbd(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a key, alone or inside text of a size.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell, ``around`` giving the size of the text
            the key is in.

    Returns:
        The key, or the text around it.
    """
    props = dict(props)
    around = props.pop("around", None)
    key = namespace.text.kbd("Shift + Tab", **props)
    if around is None:
        return key
    return namespace.text("Press ", key, " to go back.", size=around)


MATRIX = Matrix(
    component="kbd",
    render=_kbd,
    cross={
        "size": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
        "appearance": ["light", DARK],
    },
    sweep={
        "around": ["1", "3", "6", "9"],
        "viewport": [520],
    },
    groups=[
        {"around": ["2", "5"], "appearance": [DARK]},
    ],
    stage=(360, 120),
    target="kbd",
    crop="stage",
    # Not held to zero: the shadow lists the layers of both appearances, and
    # the edge of a layer a fraction of a pixel wide is rounded another way.
)

CONTRACT = Contract(
    component="kbd",
    render=lambda namespace: namespace.text.kbd("Esc", id="key"),
)


@CONTRACT.step("is a kbd element in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    key = run.server.element("key")
    assert (key.tag, key.text) == ("kbd", "Esc")


@CONTRACT.step("is shown with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    assert run.page.locator("#key").inner_text() == "Esc"


@CONTRACT.step("keeps its text after hydration", on=HYDRATED)
def _hydrated(run: Run) -> None:
    assert run.page.locator("#key").inner_text() == "Esc"
