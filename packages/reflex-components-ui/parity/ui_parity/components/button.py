"""The button: every variant, size and state, and what the keyboard does."""

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


def _button(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a button, with what a cell says it holds.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``holds`` names the children when they
            are not words alone.

    Returns:
        The button.
    """
    props = dict(props)
    holds = props.pop("holds", None)
    if holds == "icon":
        return namespace.button(rx.icon("plus"), "Add", **props)
    if holds == "link":
        return namespace.button(rx.el.a("Docs", href="#docs"), as_child=True, **props)
    return namespace.button("Save", **props)


MATRIX = Matrix(
    component="button",
    render=_button,
    cross={"variant": VARIANTS, "size": SIZES},
    sweep={
        "color_scheme": ACCENTS,
        "radius": ["none", "small", "medium", "large", "full"],
        "high_contrast": [True],
        "disabled": [True],
        "loading": [True, False],
        "holds": ["icon", "link"],
        "size": {"responsive": rx.breakpoints(initial="1", sm="4", lg="2")},
        "appearance": [DARK],
        "state": STATES,
        "viewport": [520],
    },
    groups=[
        {"variant": VARIANTS, "state": STATES, "appearance": [LIGHT, DARK]},
        {
            "variant": VARIANTS,
            "high_contrast": [True],
            "state": STATES,
            "appearance": [LIGHT, DARK],
        },
        {
            "variant": VARIANTS,
            "disabled": [True],
            "state": ["rest", HOVER],
            "appearance": [LIGHT, DARK],
        },
        {"variant": VARIANTS, "disabled": [True], "high_contrast": [True]},
        {"variant": VARIANTS, "loading": [True], "appearance": [LIGHT, DARK]},
        {"variant": ["solid", "ghost"], "loading": [True], "size": SIZES},
        {
            "variant": VARIANTS,
            "color_scheme": ["ruby", "gray", "yellow"],
            "high_contrast": [False, True],
        },
        {"variant": ["solid", "soft"], "radius": ["none", "full"], "size": SIZES},
        {"variant": VARIANTS, "holds": ["icon"]},
        {"variant": ["solid", "ghost"], "holds": ["link"], "state": STATES},
        {"holds": ["link"], "disabled": [True], "state": ["rest", HOVER]},
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="4", lg="2")},
            "variant": ["solid", "ghost"],
            "viewport": [520, 800, 1100, 1280],
        },
    ],
    stage=(200, 100),
    parts={"icon": "svg"},
    # Not held to zero. At a threshold of zero 252 of the 290 cells are equal
    # pixel for pixel, and the others differ by where they are on the page:
    # the gradients of the classic variant are dithered, by one or two steps
    # of a channel, and a few pixels on the rounded ring of the focus and on
    # the turned leaves of the spinner are anti-aliased otherwise (at most 4
    # pixels of a cell). The same props in another frame are equal.
    tolerance=0.002,
)

CONTRACT = Contract(
    component="button",
    render=lambda namespace: namespace.box(
        namespace.button(
            "Save",
            id="save",
            on_click=rx.call_script("window.saved = (window.saved || 0) + 1"),
        ),
        namespace.button("Off", id="off", disabled=True),
        namespace.button("Busy", id="busy", loading=True),
        namespace.button("Last", id="last"),
    ),
)


@CONTRACT.step("is a button with its text in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    save = run.server.element("save")
    assert (save.tag, save.text) == ("button", "Save")
    off = run.server.element("off")
    assert "disabled" in off.attributes
    assert off.attributes["data-disabled"] == "true"
    busy = run.server.element("busy")
    assert "disabled" in busy.attributes
    assert busy.attributes["data-disabled"] == "true"


@CONTRACT.step(
    "is a button that takes the focus with JavaScript disabled", on=NO_JAVASCRIPT
)
def _without_javascript(run: Run) -> None:
    save = run.page.locator("#save")
    assert save.is_visible()
    run.page.keyboard.press("Tab")
    assert run.page.evaluate("document.activeElement.id") == "save"
    assert run.page.locator("#off").is_disabled()


@CONTRACT.step("has the role and the name of a button, loading or not", on=HYDRATED)
def _role(run: Run) -> None:
    assert run.page.get_by_role("button", name="Save").get_attribute("id") == "save"
    busy = run.page.get_by_role("button", name="Busy", include_hidden=True)
    assert busy.get_attribute("id") == "busy"
    assert run.page.get_by_role("button", disabled=True).count() == 2


@CONTRACT.step("Tab skips the disabled and the loading button", on=HYDRATED)
def _tab(run: Run) -> None:
    focused = []
    for _ in range(2):
        run.page.keyboard.press("Tab")
        focused.append(run.page.evaluate("document.activeElement.id"))
    assert focused == ["save", "last"]
    assert run.page.locator("#last").evaluate(
        "element => element.matches(':focus-visible')"
    )
    run.page.keyboard.press("Shift+Tab")
    assert run.page.evaluate("document.activeElement.id") == "save"


@CONTRACT.step("Enter, Space and a click press the button", on=HYDRATED)
def _press(run: Run) -> None:
    save = run.page.locator("#save")
    save.focus()
    run.page.keyboard.press("Enter")
    run.page.wait_for_function("window.saved === 1")
    run.page.keyboard.press("Space")
    run.page.wait_for_function("window.saved === 2")
    save.click()
    run.page.wait_for_function("window.saved === 3")
    assert run.page.evaluate("document.activeElement.id") == "save"


@CONTRACT.step("a disabled button is not pressed", on=HYDRATED)
def _disabled(run: Run) -> None:
    run.page.locator("#off").click(force=True)
    run.page.locator("#busy").click(force=True)
    run.page.locator("#save").click()
    run.page.wait_for_function("window.saved === 1")
