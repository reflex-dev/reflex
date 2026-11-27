"""The section: the space above and below its content."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix


def _section(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a section whose content shows the space around it.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell.

    Returns:
        The section.
    """
    return namespace.section(
        rx.el.div("The quick brown fox", style={"border": "1px solid currentColor"}),
        **props,
    )


MATRIX = Matrix(
    component="section",
    render=_section,
    sweep={
        "size": ["1", "2", "3"],
        "style": {"background": {"background_color": "rgba(128, 128, 128, 0.2)"}},
        "appearance": [DARK],
    },
    groups=[
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
            "viewport": [520, 800, 1280],
        },
    ],
    stage=(240, 200),
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="section",
    render=lambda namespace: namespace.section(
        "content", id="section", custom_attrs={"aria-label": "Pricing"}
    ),
)


@CONTRACT.step("is a section in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    section = run.server.element("section")
    assert (section.tag, section.text) == ("section", "content")


@CONTRACT.step("is shown with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    assert run.page.locator("#section").is_visible()


@CONTRACT.step("is a region with its label after hydration", on=HYDRATED)
def _hydrated(run: Run) -> None:
    region = run.page.get_by_role("region", name="Pricing")
    assert region.get_attribute("id") == "section"
