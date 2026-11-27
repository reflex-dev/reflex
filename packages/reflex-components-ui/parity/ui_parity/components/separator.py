"""The separator: a line of a size, an orientation and a color."""

from __future__ import annotations

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix
from ui_parity.samples import ACCENTS

MATRIX = Matrix(
    component="separator",
    cross={
        "size": ["1", "2", "3", "4"],
        "orientation": ["horizontal", "vertical"],
    },
    sweep={
        "color_scheme": ACCENTS,
        "decorative": [True, False],
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        {"color_scheme": ["ruby", "gray"], "appearance": [DARK]},
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
            "orientation": {
                "responsive": rx.breakpoints(initial="vertical", md="horizontal")
            },
            "viewport": [520, 800, 1100, 1280],
        },
    ],
    stage=(200, 120),
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="separator",
    render=lambda namespace: namespace.box(
        namespace.separator(id="decorative"),
        namespace.separator(decorative=False, id="semantic"),
    ),
)


@CONTRACT.step("is a span, with a role when it is not decorative", on=SERVER)
def _server_render(run: Run) -> None:
    decorative = run.server.element("decorative")
    assert (decorative.tag, decorative.text) == ("span", "")
    assert "role" not in decorative.attributes
    assert run.server.element("semantic").attributes["role"] == "separator"


@CONTRACT.step(
    "is a line across its container with JavaScript disabled", on=NO_JAVASCRIPT
)
def _without_javascript(run: Run) -> None:
    box = run.page.locator("#decorative").bounding_box()
    assert box is not None
    assert box["height"] == 1
    assert box["width"] > 100


@CONTRACT.step("only the semantic one is in the accessibility tree", on=HYDRATED)
def _roles(run: Run) -> None:
    separators = run.page.get_by_role("separator")
    assert separators.count() == 1
    assert separators.get_attribute("id") == "semantic"
