"""The spacer: the room between the children of a flex container."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix
from ui_parity.samples import tiles


def _spacer(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a flex container with a spacer between its children.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell: ``direction`` is the container's, the
            rest are the spacer's.

    Returns:
        The container.
    """
    props = dict(props)
    direction = props.pop("direction", "row")
    first, second = tiles(("quick", "fox"))
    return namespace.flex(
        first,
        namespace.spacer(custom_attrs={"data-spacer": ""}, **props),
        second,
        direction=direction,
        style={"height": "100px"},
    )


MATRIX = Matrix(
    component="spacer",
    render=_spacer,
    sweep={
        "direction": ["row", "column", "row-reverse"],
        "style": {
            "outlined": {"border": "1px dashed currentColor"},
            "bounded": {"max_width": "40px"},
        },
        "appearance": [DARK],
        "viewport": [520],
    },
    stage=(240, 140),
    target="[data-spacer]",
    crop="stage",
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="spacer",
    render=lambda namespace: namespace.flex(
        namespace.box("left", id="left"),
        namespace.spacer(id="spacer"),
        namespace.box("right", id="right"),
        id="row",
    ),
)


@CONTRACT.step("is an empty div in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    spacer = run.server.element("spacer")
    assert (spacer.tag, spacer.text) == ("div", "")


@CONTRACT.step("pushes its siblings apart with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    _pushes_apart(run)


@CONTRACT.step("pushes its siblings apart after hydration", on=HYDRATED)
def _hydrated(run: Run) -> None:
    _pushes_apart(run)


def _pushes_apart(run: Run) -> None:
    """Check that the siblings of the spacer are at the ends of the row.

    Args:
        run: The run of the step.
    """
    row = run.page.locator("#row").bounding_box()
    left = run.page.locator("#left").bounding_box()
    right = run.page.locator("#right").bounding_box()
    assert row is not None
    assert left is not None
    assert right is not None
    assert left["x"] == row["x"]
    assert right["x"] + right["width"] == row["x"] + row["width"]
