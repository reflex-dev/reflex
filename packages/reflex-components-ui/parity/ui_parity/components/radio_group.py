"""The radio group: every variant, size and state, and what native inputs give it."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import ACTIVE, DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import ACCENTS, focused, wait_for_text

VARIANTS = ["classic", "surface", "soft"]
SIZES = ["1", "2", "3"]
STATES = ["rest", HOVER, FOCUS_VISIBLE, ACTIVE]
ITEMS = ["One", "Two", "Three"]
# The first radio button of the group: a button of Radix, an input here.
TARGET = ("button", "input")


def _group(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a radio group from a list of items.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell.

    Returns:
        The group.
    """
    return namespace.radio_group(ITEMS, **props)


MATRIX = Matrix(
    component="radio_group",
    render=_group,
    base={"default_value": "One"},
    cross={"variant": VARIANTS, "size": SIZES, "default_value": ["One", "Two"]},
    sweep={
        "color_scheme": ACCENTS,
        "high_contrast": [True],
        "disabled": [True],
        "direction": ["row", "column", "row-reverse", "column-reverse"],
        "spacing": ["1", "5"],
        "appearance": [DARK],
        "state": STATES,
    },
    groups=[
        {
            "variant": VARIANTS,
            "high_contrast": [False, True],
            "appearance": [LIGHT, DARK],
        },
        {"variant": VARIANTS, "disabled": [True], "appearance": [LIGHT, DARK]},
        {"variant": VARIANTS, "default_value": ["One", "Two"], "state": STATES},
        {
            "variant": VARIANTS,
            "color_scheme": ["ruby", "gray", "yellow"],
            "high_contrast": [False, True],
        },
    ],
    stage=(220, 110),
    crop="stage",
    target=TARGET,
    # Not held to zero. A circle is anti-aliased by where it is on the page:
    # with the two frames of a cell swapped, each system is equal pixel for
    # pixel to the other one in the same place, and differs from itself in
    # the other place by the same pixels. At the default threshold 26 of the
    # 117 cells differ, by at most 88 pixels of 24200.
    tolerance=0.004,
)


class RadioGroupState(rx.State):
    """What the radio groups of the contract are bound to."""

    bound: str = "a"
    seen: list[str] = []
    submitted: dict[str, str] = {}
    submissions: int = 0

    @rx.event
    def set_bound(self, value: str):
        """Follow the bound group.

        Args:
            value: The value of its checked item.
        """
        self.bound = value

    @rx.event
    def see(self, value: str):
        """Keep what a change handed over.

        Args:
            value: The value of the checked item.
        """
        self.seen.append(value)

    @rx.event
    def pick_last(self):
        """Change the bound value from outside the group."""
        self.bound = "c"

    @rx.event
    def submit(self, data: dict[str, str]):
        """Keep what a form submitted.

        Args:
            data: The values of the form.
        """
        self.submitted = data
        self.submissions += 1


CONTRACT = Contract(
    component="radio_group",
    render=lambda namespace: namespace.box(
        rx.el.div(
            namespace.radio_group(ITEMS, on_change=RadioGroupState.see), id="pick"
        ),
        rx.el.div(
            namespace.radio_group.root(
                namespace.radio_group.item("Red", value="red"),
                namespace.radio_group.item("Green", value="green", disabled=True),
                namespace.radio_group.item("Blue", value="blue"),
                default_value="red",
                on_change=RadioGroupState.see,
            ),
            id="colors",
        ),
        rx.el.div(
            namespace.radio_group(
                ["a", "b", "c"],
                value=RadioGroupState.bound,
                on_change=RadioGroupState.set_bound,
            ),
            id="bound",
        ),
        rx.el.button("Last", id="last", on_click=RadioGroupState.pick_last),
        rx.el.div(namespace.radio_group(["x", "y"], disabled=True), id="off"),
        rx.el.form(
            namespace.radio_group(["s", "m", "l"], name="size", default_value="m"),
            namespace.radio_group.root(
                namespace.radio_group.item("Yes", value="yes"),
                namespace.radio_group.item("No", value="no"),
                name="answer",
                required=True,
            ),
            rx.el.button("Send", id="send", type="submit"),
            on_submit=RadioGroupState.submit,
            id="form",
        ),
        rx.el.span(RadioGroupState.seen.to_string(), id="seen"),
        rx.el.span(RadioGroupState.bound, id="bound-value"),
        rx.el.span(RadioGroupState.submitted.to_string(), id="submitted"),
        rx.el.span(RadioGroupState.submissions.to_string(), id="submissions"),
    ),
)

# The text of the checked radio buttons of a group, by the id of its frame.
CHECKED = (
    "id => [...document.getElementById(id).querySelectorAll('label')]"
    ".filter(label => label.querySelector(':checked, [aria-checked=true]'))"
    ".map(label => label.textContent)"
)
# How long a key is held, in milliseconds.
HELD = 60
# The text of the item that has the focus.
FOCUSED_ITEM = "document.activeElement.closest('label')?.textContent"


def _wait_for_checked(run: Run, group: str, items: list[str]) -> None:
    """Wait until the checked items of a group are the ones expected.

    Args:
        run: The run, on a page.
        group: The id of the frame of the group.
        items: The text of each item that is to be checked.
    """
    run.page.wait_for_function(
        f"([id, items]) => JSON.stringify(({CHECKED})(id)) === items",
        arg=[group, json.dumps(items)],
    )


@CONTRACT.step("its items are in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    assert run.server.element("pick").text == "OneTwoThree"
    assert run.server.element("colors").text == "RedGreenBlue"


@CONTRACT.step("checks one item of a group with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    page = run.page
    page.set_default_timeout(3000)
    page.locator("#pick").get_by_text("Two").click()
    _wait_for_checked(run, "pick", ["Two"])
    page.locator("#pick").get_by_text("Three").click()
    _wait_for_checked(run, "pick", ["Three"])
    _wait_for_checked(run, "colors", ["Red"])
    _wait_for_checked(run, "form", ["m"])


@CONTRACT.step("has the roles, the names and the states of a group of radio buttons")
def _role(run: Run) -> None:
    page = run.page
    assert page.get_by_role("radiogroup").count() == 6
    pick = page.locator("#pick")
    assert pick.get_by_role("radio").count() == 3
    assert not pick.get_by_role("radio", name="One").is_checked()
    colors = page.locator("#colors")
    assert colors.get_by_role("radio", name="Red", checked=True).count() == 1
    assert colors.get_by_role("radio", name="Green", disabled=True).count() == 1
    assert page.locator("#off").get_by_role("radio", disabled=True).count() == 2


@CONTRACT.step("Tab stops once in each group, on its checked item")
def _tab(run: Run) -> None:
    page = run.page
    stops = []
    for _ in range(4):
        page.keyboard.press("Tab")
        stops.append(page.evaluate(FOCUSED_ITEM) or focused(page))
    assert stops == ["One", "Red", "a", "last"]
    _wait_for_checked(run, "pick", [])


@CONTRACT.step("Shift+Tab into a group with nothing checked stops on its first item")
def _shift_tab(run: Run) -> None:
    page = run.page
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    assert page.evaluate(FOCUSED_ITEM) == "Red"
    page.keyboard.press("Shift+Tab")
    assert page.evaluate(FOCUSED_ITEM) == "One"


@CONTRACT.step("the arrow keys move through a group and check, past a disabled item")
def _arrows(run: Run) -> None:
    page = run.page
    page.keyboard.press("Tab")
    visited = []
    for key in ("ArrowDown", "ArrowRight", "ArrowDown", "ArrowUp", "ArrowLeft"):
        # Held as long as a finger holds it: Radix checks the item the focus
        # moves to only while the key is still down.
        page.keyboard.press(key, delay=HELD)
        visited.append(page.evaluate(FOCUSED_ITEM))
        _wait_for_checked(run, "pick", [visited[-1]])
    assert visited == ["Two", "Three", "One", "Three", "Two"]
    wait_for_text(page, "seen", '["Two","Three","One","Three","Two"]')
    page.keyboard.press("Tab")
    page.keyboard.press("ArrowDown", delay=HELD)
    assert page.evaluate(FOCUSED_ITEM) == "Blue"
    _wait_for_checked(run, "colors", ["Blue"])
    page.keyboard.press("ArrowDown", delay=HELD)
    _wait_for_checked(run, "colors", ["Red"])


@CONTRACT.step("Space and a click on a label check an item, and say so")
def _check(run: Run) -> None:
    page = run.page
    page.keyboard.press("Tab")
    page.keyboard.press("Space")
    _wait_for_checked(run, "pick", ["One"])
    page.locator("#pick").get_by_text("Three").click()
    _wait_for_checked(run, "pick", ["Three"])
    page.locator("#pick").get_by_text("Three").click()
    _wait_for_checked(run, "pick", ["Three"])
    wait_for_text(page, "seen", '["One","Three"]')


@CONTRACT.step("Enter on a radio button does not submit its form")
def _enter_in_form(run: Run) -> None:
    page = run.page
    page.locator("#form").get_by_text("Yes").click()
    page.keyboard.press("Enter")
    page.locator("#last").click()
    wait_for_text(page, "bound-value", "c")
    assert page.locator("#submissions").text_content() == "0"


@CONTRACT.step("a disabled group and a disabled item are not checked")
def _disabled(run: Run) -> None:
    page = run.page
    page.locator("#off").get_by_text("x").click(force=True)
    _wait_for_checked(run, "off", [])
    page.locator("#colors").get_by_text("Green").click(force=True)
    _wait_for_checked(run, "colors", ["Red"])


@CONTRACT.step("follows the state it is bound to")
def _bound(run: Run) -> None:
    page = run.page
    _wait_for_checked(run, "bound", ["a"])
    page.locator("#bound").get_by_text("b").click()
    wait_for_text(page, "bound-value", "b")
    _wait_for_checked(run, "bound", ["b"])
    page.locator("#last").click()
    wait_for_text(page, "bound-value", "c")
    _wait_for_checked(run, "bound", ["c"])


@CONTRACT.step("submits the value of its checked item with a form")
def _submit(run: Run) -> None:
    page = run.page
    page.locator("#form").get_by_text("No").click()
    page.locator("#send").click()
    wait_for_text(page, "submissions", "1")
    assert page.locator("#submitted").text_content() == '{"size":"m","answer":"no"}'


@CONTRACT.step("a required group holds its form back until an item is checked")
def _required(run: Run) -> None:
    page = run.page
    page.locator("#send").click()
    # An event that does reach the server comes back after the blocked one.
    page.locator("#last").click()
    wait_for_text(page, "bound-value", "c")
    assert page.locator("#submissions").text_content() == "0"
    page.locator("#form").get_by_text("Yes").click()
    page.locator("#send").click()
    wait_for_text(page, "submissions", "1")
