"""The radio group: every variant, size and state, and what native inputs give it."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import ACTIVE, DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import ACCENTS, focused, wait_for_text, wait_for_value

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
    parts={
        "root": "[role=radiogroup]",
        "box": ("button::before", "input::before"),
        "dot": ("button::after", "input::after"),
    },
    # Not held to zero. At a threshold of zero the cells that differ do so
    # by where they are on the page: the circle of a radio button and its
    # focus ring are anti-aliased by it. At the default threshold the worst
    # cell differs by 17 pixels.
    tolerance=0.001,
)


class RadioGroupState(rx.State):
    """What the radio groups of the contract are bound to."""

    bound: rx.Field[str] = rx.field("a")
    seen: rx.Field[list[str]] = rx.field(default_factory=list)
    submitted: rx.Field[dict[str, str]] = rx.field(default_factory=dict)
    submissions: rx.Field[int] = rx.field(0)

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
# The text of the item that has the focus, or nothing when no item has it.
FOCUSED_ITEM = "(document.activeElement.closest('label')?.textContent ?? null)"
# Whether the focus is in the group with nothing checked.
IN_PICK = "document.activeElement.closest('#pick') !== null"


def _wait_for_checked(run: Run, group: str, items: list[str]) -> None:
    """Wait until the checked items of a group are the ones expected.

    Args:
        run: The run, on a page.
        group: The id of the frame of the group.
        items: The text of each item that is to be checked.
    """
    wait_for_value(run.page, f"({CHECKED})({json.dumps(group)})", items)


def _wait_for_focus(run: Run, item: str) -> None:
    """Wait until an item has the focus.

    Args:
        run: The run, on a page.
        item: The text of the item.
    """
    wait_for_value(run.page, FOCUSED_ITEM, item)


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


@CONTRACT.step("Shift+Tab stops once in a group with nothing checked")
def _shift_tab_once(run: Run) -> None:
    page = run.page
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    _wait_for_focus(run, "Red")
    inside = []
    for _ in range(2):
        page.keyboard.press("Shift+Tab")
        inside.append(page.evaluate(IN_PICK))
    assert inside == [True, False]
    _wait_for_checked(run, "pick", [])


@CONTRACT.step("Shift+Tab into a group with nothing checked stops on its first item")
def _shift_tab(run: Run) -> None:
    page = run.page
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    _wait_for_focus(run, "Red")
    page.keyboard.press("Shift+Tab")
    _wait_for_focus(run, "One")


@CONTRACT.step("the arrow keys move through a group and check, past a disabled item")
def _arrows(run: Run) -> None:
    page = run.page
    page.keyboard.press("Tab")
    for key, item in (
        ("ArrowDown", "Two"),
        ("ArrowRight", "Three"),
        ("ArrowUp", "Two"),
        ("ArrowLeft", "One"),
    ):
        # Held as long as a finger holds it: Radix checks the item the focus
        # moves to only while the key is still down.
        page.keyboard.press(key, delay=HELD)
        _wait_for_focus(run, item)
        _wait_for_checked(run, "pick", [item])
    wait_for_text(page, "seen", '["Two","Three","Two","One"]')
    page.keyboard.press("Tab")
    _wait_for_focus(run, "Red")
    page.keyboard.press("ArrowDown", delay=HELD)
    _wait_for_focus(run, "Blue")
    _wait_for_checked(run, "colors", ["Blue"])
    page.keyboard.press("ArrowUp", delay=HELD)
    _wait_for_focus(run, "Red")
    _wait_for_checked(run, "colors", ["Red"])


@CONTRACT.step("the arrow keys go round at the ends of a group")
def _arrows_round(run: Run) -> None:
    page = run.page
    page.keyboard.press("Tab")
    _wait_for_focus(run, "One")
    page.keyboard.press("ArrowUp", delay=HELD)
    _wait_for_focus(run, "Three")
    _wait_for_checked(run, "pick", ["Three"])
    page.keyboard.press("ArrowDown", delay=HELD)
    _wait_for_focus(run, "One")
    _wait_for_checked(run, "pick", ["One"])


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
