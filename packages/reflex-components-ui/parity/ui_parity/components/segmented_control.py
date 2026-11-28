"""The segmented control: every variant, size and state, and how its items are chosen."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.look import FOCUS_WITHIN
from ui_parity.matrix import ACTIVE, DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import focused, wait_for_text

VARIANTS = ["surface", "classic"]
SIZES = ["1", "2", "3"]
RADII = ["none", "small", "medium", "large", "full"]
STATES = ["rest", HOVER, FOCUS_VISIBLE, ACTIVE]
# The second item: a button of Radix, a label around a radio button here.
TARGET = ("button:nth-child(2)", "label:nth-child(2)")
MANY = [str(number) for number in range(1, 13)]


def _control(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a segmented control.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the root. ``holds`` says what the items are when
            they are not three words.

    Returns:
        The control.
    """
    props = dict(props)
    holds = props.pop("holds", None)
    item = namespace.segmented_control.item
    if holds == "many":
        items = [item(number, value=number) for number in MANY]
    elif holds == "icons":
        items = [
            item(rx.icon("sun", size=14), "Light", value="1"),
            item(rx.icon("moon", size=14), "Dark", value="2"),
        ]
    else:
        items = [
            item("One", value="1"),
            item("Two", value="2"),
            item("Three", value="3"),
        ]
    return namespace.segmented_control.root(*items, **props)


MATRIX = Matrix(
    component="segmented_control",
    render=_control,
    base={"default_value": "1"},
    cross={"variant": VARIANTS, "size": SIZES, "default_value": ["1", "2", "3"]},
    sweep={
        "radius": RADII,
        "color_scheme": ["ruby", "gray"],
        "holds": ["many", "icons"],
        "default_value": {"none": None},
        "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
        "appearance": [DARK],
        "state": STATES,
        "viewport": [520],
    },
    groups=[
        {
            "variant": VARIANTS,
            "default_value": ["1", "2"],
            "state": STATES,
            "appearance": [LIGHT, DARK],
        },
        {"radius": RADII, "size": SIZES, "variant": VARIANTS},
        {"holds": ["many"], "default_value": ["1", "11", "12"], "size": ["1"]},
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
            "viewport": [520, 800, 1100],
        },
    ],
    stage=(420, 80),
    crop="stage",
    target=TARGET,
    parts={
        "root": "[role=radiogroup]",
        "indicator": "[role=radiogroup] > div",
    },
    # The focus is on the item of Radix and on the radio button in the item
    # here.
    states={FOCUS_VISIBLE: FOCUS_WITHIN},
    # Not held to zero. At a threshold of zero 87 of the 103 cells are equal
    # pixel for pixel, and the others differ by where they are on the page:
    # the translucent fills of the control and of what marks the chosen item
    # are dithered by a step of a channel. At the default threshold 3 cells
    # differ, by at most 3 pixels of 33600 on a rounded corner.
    tolerance=0.0001,
)


class SegmentedControlState(rx.State):
    """What the segmented controls of the contract are bound to."""

    bound: str = "a"
    seen: list[str] = []
    submitted: dict[str, Any] = {}
    submissions: int = 0

    @rx.event
    def set_bound(self, value: str | list[str]):
        """Follow the bound control.

        Args:
            value: The value of its chosen item.
        """
        self.bound = str(value)

    @rx.event
    def see(self, value: str | list[str]):
        """Keep what a change handed over.

        Args:
            value: The value of the chosen item.
        """
        self.seen.append(str(value))

    @rx.event
    def pick_last(self):
        """Change the bound value from outside the control."""
        self.bound = "c"

    @rx.event
    def submit(self, data: dict[str, Any]):
        """Keep what a form submitted.

        Args:
            data: The values of the form.
        """
        self.submitted = data
        self.submissions += 1


def _items(namespace: Any, *values: str) -> list[Any]:
    """Create the items of a control, each with its value as its text.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        *values: The value of each item.

    Returns:
        The items.
    """
    return [namespace.segmented_control.item(value, value=value) for value in values]


CONTRACT = Contract(
    component="segmented_control",
    render=lambda namespace: namespace.box(
        rx.el.div(
            namespace.segmented_control.root(
                *_items(namespace, "One", "Two", "Three"),
                on_change=SegmentedControlState.see,
            ),
            id="pick",
        ),
        rx.el.div(
            namespace.segmented_control.root(
                *_items(namespace, "s", "m", "l"), default_value="m"
            ),
            id="sized",
        ),
        rx.el.div(
            namespace.segmented_control.root(
                rx.foreach(
                    ["a", "b", "c"],
                    lambda value: namespace.segmented_control.item(value, value=value),
                ),
                value=SegmentedControlState.bound,
                on_change=SegmentedControlState.set_bound,
            ),
            id="bound",
        ),
        rx.el.button("Last", id="last", on_click=SegmentedControlState.pick_last),
        rx.el.form(
            namespace.segmented_control.root(
                *_items(namespace, "x", "y"), default_value="x"
            ),
            rx.el.input(name="note", default_value="hi", id="note"),
            rx.el.button("Send", id="send", type="submit"),
            on_submit=SegmentedControlState.submit,
            id="form",
        ),
        rx.el.span(SegmentedControlState.seen.to_string(), id="seen"),
        rx.el.span(SegmentedControlState.bound, id="bound-value"),
        rx.el.span(SegmentedControlState.submitted.to_string(), id="submitted"),
        rx.el.span(SegmentedControlState.submissions.to_string(), id="submissions"),
    ),
)

# An item is a button of Radix and a label around a radio button here.
ITEMS = "button[role=radio], label"
# The text of the chosen items of a control, by the id of its frame.
CHOSEN = (
    f"id => [...document.getElementById(id).querySelectorAll('{ITEMS}')]"
    ".filter(item => item.matches('[aria-checked=true], :has(:checked)'))"
    ".map(item => item.querySelector('span > span').textContent)"
)
# The text of the item that has the focus.
FOCUSED_ITEM = f"document.activeElement.closest('{ITEMS}')?.querySelector('span > span').textContent"
# A click on the text of an item is forced: Playwright looks for the element
# under the pointer, which is the other one of the two texts of the item.
# How long a key is held, in milliseconds.
HELD = 60


def _wait_for_chosen(run: Run, control: str, items: list[str]) -> None:
    """Wait until the chosen items of a control are the ones expected.

    Args:
        run: The run, on a page.
        control: The id of the frame of the control.
        items: The text of each item that is to be chosen.
    """
    run.page.wait_for_function(
        f"([id, items]) => JSON.stringify(({CHOSEN})(id)) === items",
        arg=[control, json.dumps(items)],
    )


def _wait_for_focus(run: Run, item: str) -> None:
    """Wait until an item has the focus.

    Args:
        run: The run, on a page.
        item: The text of the item.
    """
    run.page.wait_for_function(f"item => {FOCUSED_ITEM} === item", arg=item)


@CONTRACT.step("its items are in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    assert run.server.element("pick").text == "OneOneTwoTwoThreeThree"


@CONTRACT.step("chooses an item with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    page = run.page
    page.set_default_timeout(3000)
    _wait_for_chosen(run, "sized", ["m"])
    page.locator("#pick").get_by_text("Two").first.click(force=True)
    _wait_for_chosen(run, "pick", ["Two"])
    page.locator("#pick").get_by_text("Three").first.click(force=True)
    _wait_for_chosen(run, "pick", ["Three"])


@CONTRACT.step("is a group of radio buttons with their names and states")
def _role(run: Run) -> None:
    page = run.page
    assert page.get_by_role("radiogroup").count() == 4
    pick = page.locator("#pick")
    assert pick.get_by_role("radio").count() == 3
    assert not pick.get_by_role("radio", name="One", exact=True).is_checked()
    sized = page.locator("#sized")
    assert sized.get_by_role("radio", name="m", exact=True, checked=True).count() == 1
    assert sized.get_by_role("radio", checked=True).count() == 1


@CONTRACT.step("Tab stops once in each control, on its chosen item")
def _tab(run: Run) -> None:
    page = run.page
    stops = []
    for _ in range(4):
        page.keyboard.press("Tab")
        stops.append(page.evaluate(FOCUSED_ITEM) or focused(page))
    assert stops == ["One", "m", "a", "last"]
    _wait_for_chosen(run, "pick", [])


@CONTRACT.step("the arrow keys, Home and End move the focus without choosing")
def _arrows(run: Run) -> None:
    page = run.page
    page.keyboard.press("Tab")
    for key, item in (
        ("ArrowRight", "Two"),
        ("ArrowDown", "Three"),
        ("ArrowRight", "One"),
        ("ArrowLeft", "Three"),
        ("ArrowUp", "Two"),
        ("Home", "One"),
        ("End", "Three"),
    ):
        page.keyboard.press(key, delay=HELD)
        _wait_for_focus(run, item)
    _wait_for_chosen(run, "pick", [])
    assert page.locator("#seen").text_content() == "[]"


@CONTRACT.step("Space, Enter and a click choose an item, and say so")
def _choose(run: Run) -> None:
    page = run.page
    page.keyboard.press("Tab")
    page.keyboard.press("Space")
    _wait_for_chosen(run, "pick", ["One"])
    page.keyboard.press("ArrowRight", delay=HELD)
    _wait_for_focus(run, "Two")
    page.keyboard.press("Enter")
    _wait_for_chosen(run, "pick", ["Two"])
    page.locator("#pick").get_by_text("Three").first.click(force=True)
    _wait_for_chosen(run, "pick", ["Three"])
    wait_for_text(page, "seen", '["One","Two","Three"]')


@CONTRACT.step("the chosen item stays chosen when it is chosen again")
def _again(run: Run) -> None:
    page = run.page
    page.locator("#sized").get_by_text("m").first.click(force=True)
    page.keyboard.press("Space")
    page.keyboard.press("Enter")
    _wait_for_chosen(run, "sized", ["m"])
    page.locator("#pick").get_by_text("One").first.click(force=True)
    wait_for_text(page, "seen", '["One"]')
    page.locator("#pick").get_by_text("One").first.click(force=True)
    page.locator("#pick").get_by_text("Two").first.click(force=True)
    wait_for_text(page, "seen", '["One","Two"]')


@CONTRACT.step("follows the state it is bound to")
def _bound(run: Run) -> None:
    page = run.page
    _wait_for_chosen(run, "bound", ["a"])
    page.locator("#bound").get_by_text("b").first.click(force=True)
    wait_for_text(page, "bound-value", "b")
    _wait_for_chosen(run, "bound", ["b"])
    page.locator("#last").click()
    wait_for_text(page, "bound-value", "c")
    _wait_for_chosen(run, "bound", ["c"])


@CONTRACT.step("is no value of the form it is in")
def _submit(run: Run) -> None:
    page = run.page
    page.locator("#form").get_by_text("y").first.click(force=True)
    page.locator("#send").click()
    wait_for_text(page, "submissions", "1")
    assert page.locator("#submitted").text_content() == '{"note":"hi"}'
