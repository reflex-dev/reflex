"""The icon button: a square button around one icon."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import ACTIVE, DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import ACCENTS

VARIANTS = ["classic", "solid", "soft", "surface", "outline", "ghost"]
SIZES = ["1", "2", "3", "4"]
STATES = ["rest", HOVER, FOCUS_VISIBLE, ACTIVE]
RESPONSIVE = rx.breakpoints(initial="1", sm="4", lg="2")


def _icon_button(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create an icon button around a plus, named or passed as an icon.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``holds`` says whether the icon is
            created by the caller.

    Returns:
        The icon button.
    """
    props = dict(props)
    if props.pop("holds", None) == "icon":
        return namespace.icon_button(rx.icon("plus", size=18), **props)
    return namespace.icon_button("plus", **props)


MATRIX = Matrix(
    component="icon_button",
    render=_icon_button,
    cross={"variant": VARIANTS, "size": SIZES},
    sweep={
        "color_scheme": ACCENTS,
        "radius": ["none", "small", "medium", "large", "full"],
        "high_contrast": [True],
        "disabled": [True],
        "loading": [True, False],
        "holds": ["icon"],
        "size": {"responsive": RESPONSIVE},
        "appearance": [DARK],
        "state": STATES,
        "viewport": [520],
    },
    groups=[
        {"variant": VARIANTS, "state": STATES, "appearance": [LIGHT, DARK]},
        {"variant": VARIANTS, "high_contrast": [True], "appearance": [LIGHT, DARK]},
        {"variant": VARIANTS, "disabled": [True], "appearance": [LIGHT, DARK]},
        {"variant": ["solid", "ghost"], "loading": [True], "size": SIZES},
        {"variant": ["solid", "soft"], "radius": ["none", "full"], "size": SIZES},
        {
            "size": {"responsive": RESPONSIVE},
            "variant": ["solid", "ghost"],
            "viewport": [520, 800, 1100, 1280],
        },
    ],
    stage=(140, 100),
    parts={"icon": "svg"},
    # Not held to zero, for what the button is not: the gradients of the
    # classic variant are dithered by where they are on the page, and the
    # rounded ring of the focus is anti-aliased by it.
    tolerance=0.002,
)

CONTRACT = Contract(
    component="icon_button",
    render=lambda namespace: namespace.box(
        namespace.icon_button(
            "plus",
            id="add",
            custom_attrs={"aria-label": "Add"},
            on_click=rx.call_script("window.added = (window.added || 0) + 1"),
        ),
        namespace.icon_button(
            "trash", id="off", disabled=True, custom_attrs={"aria-label": "Remove"}
        ),
    ),
)


@CONTRACT.step("is a button around an icon in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    add = run.server.element("add")
    assert (add.tag, add.text, add.attributes["aria-label"]) == ("button", "", "Add")
    off = run.server.element("off")
    assert "disabled" in off.attributes
    assert off.attributes["data-disabled"] == "true"


@CONTRACT.step(
    "shows its icon and takes the focus with JavaScript disabled", on=NO_JAVASCRIPT
)
def _without_javascript(run: Run) -> None:
    assert run.page.locator("#add svg").is_visible()
    run.page.keyboard.press("Tab")
    assert run.page.evaluate("document.activeElement.id") == "add"


@CONTRACT.step("has the role of a button and the name it is given", on=HYDRATED)
def _role(run: Run) -> None:
    assert run.page.get_by_role("button", name="Add").get_attribute("id") == "add"
    assert run.page.get_by_role("button", name="Remove").is_disabled()


@CONTRACT.step("Enter, Space and a click press the button", on=HYDRATED)
def _press(run: Run) -> None:
    add = run.page.locator("#add")
    run.page.keyboard.press("Tab")
    assert add.evaluate("element => element.matches(':focus-visible')")
    run.page.keyboard.press("Enter")
    run.page.wait_for_function("window.added === 1")
    run.page.keyboard.press("Space")
    run.page.wait_for_function("window.added === 2")
    add.click()
    run.page.wait_for_function("window.added === 3")
