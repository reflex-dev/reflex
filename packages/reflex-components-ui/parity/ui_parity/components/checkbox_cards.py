"""Checkbox cards: every variant, size and state, and what native checkboxes give them."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.look import FOCUS_WITHIN
from ui_parity.matrix import ACTIVE, DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import ACCENTS, focused, wait_for_text

VARIANTS = ["surface", "classic"]
SIZES = ["1", "2", "3"]
STATES = ["rest", HOVER, FOCUS_VISIBLE, ACTIVE]
# The first card: a label in both systems.
TARGET = "label"
# The checkbox at the end of the first card: a button of Radix, an input here.
CHECKBOX = ("label > button", "label > input")


def _cards(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create checkbox cards.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the root. ``holds`` says what the cards hold when
            it is not words alone.

    Returns:
        The cards: the first one checked unless the cell says otherwise, and
        the last one disabled.
    """
    props = dict(props)
    holds = props.pop("holds", None)
    first: list[Any] = ["One"]
    if holds == "icon":
        first = [rx.icon("star"), "One"]
    return namespace.checkbox_cards.root(
        namespace.checkbox_cards.item(*first, value="1"),
        namespace.checkbox_cards.item("Two", value="2"),
        namespace.checkbox_cards.item("Three", value="3", disabled=True),
        **props,
    )


MATRIX = Matrix(
    component="checkbox_cards",
    render=_cards,
    base={"default_value": ["1"], "columns": "3", "gap": "2"},
    cross={"variant": VARIANTS, "size": SIZES},
    sweep={
        "default_value": {"none": [], "all": ["1", "2", "3"]},
        "color_scheme": ACCENTS,
        "high_contrast": [True],
        "disabled": [True],
        "holds": ["icon"],
        "columns": {"default": None, "1": "1"},
        "gap": {"default": None, "5": "5"},
        "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
        "appearance": [DARK],
        "state": STATES,
        "viewport": [520],
    },
    groups=[
        {
            "variant": VARIANTS,
            "high_contrast": [False, True],
            "appearance": [LIGHT, DARK],
        },
        {
            "variant": VARIANTS,
            "disabled": [True],
            "default_value": {"all": ["1", "2", "3"]},
            "appearance": [LIGHT, DARK],
        },
        {"variant": VARIANTS, "state": STATES, "appearance": [LIGHT, DARK]},
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
            "viewport": [520, 800, 1100],
        },
    ],
    stage=(420, 150),
    crop="stage",
    target=TARGET,
    parts={"checkbox": CHECKBOX},
    # The focus is on the checkbox inside the card.
    states={FOCUS_VISIBLE: FOCUS_WITHIN},
    # Not held to zero, as the matrix of the radio cards is not: a card is
    # dithered and anti-aliased by where it is on the page, and the check is
    # a mask here. At the default threshold 49 of the 79 cells differ, by at
    # most 4 pixels of 63000.
    tolerance=0.0002,
)


class CheckboxCardsState(rx.State):
    """What the checkbox cards of the contract are bound to."""

    bound: list[str] = ["a"]
    seen: list[list[str]] = []
    submitted: dict[str, Any] = {}
    submissions: int = 0

    @rx.event
    def set_bound(self, values: list[str]):
        """Follow the bound group.

        Args:
            values: The values of its checked cards.
        """
        self.bound = values

    @rx.event
    def see(self, values: list[str]):
        """Keep what a change handed over.

        Args:
            values: The values of the checked cards.
        """
        self.seen.append(values)

    @rx.event
    def pick_last(self):
        """Change the bound value from outside the group."""
        self.bound = ["c"]

    @rx.event
    def submit(self, data: dict[str, Any]):
        """Keep what a form submitted.

        Args:
            data: The values of the form.
        """
        self.submitted = data
        self.submissions += 1


def _items(namespace: Any, *values: str) -> list[Any]:
    """Create the cards of a group, each with its value as its text.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        *values: The value of each card.

    Returns:
        The cards.
    """
    return [namespace.checkbox_cards.item(value, value=value) for value in values]


CONTRACT = Contract(
    component="checkbox_cards",
    render=lambda namespace: namespace.box(
        rx.el.div(
            namespace.checkbox_cards.root(
                *_items(namespace, "One", "Two", "Three"),
                on_value_change=CheckboxCardsState.see,
            ),
            id="pick",
        ),
        rx.el.div(
            namespace.checkbox_cards.root(
                namespace.checkbox_cards.item("Red", value="red"),
                namespace.checkbox_cards.item("Green", value="green", disabled=True),
                namespace.checkbox_cards.item("Blue", value="blue"),
                default_value=["red"],
            ),
            id="colors",
        ),
        rx.el.div(
            namespace.checkbox_cards.root(
                *_items(namespace, "a", "b", "c"),
                value=CheckboxCardsState.bound,
                on_value_change=CheckboxCardsState.set_bound,
            ),
            id="bound",
        ),
        rx.el.button("Last", id="last", on_click=CheckboxCardsState.pick_last),
        rx.el.div(
            namespace.checkbox_cards.root(*_items(namespace, "x", "y"), disabled=True),
            id="off",
        ),
        rx.el.form(
            namespace.checkbox_cards.root(
                *_items(namespace, "s", "m", "l"), name="size", default_value=["m"]
            ),
            rx.el.button("Send", id="send", type="submit"),
            on_submit=CheckboxCardsState.submit,
            id="form",
        ),
        rx.el.span(CheckboxCardsState.seen.to_string(), id="seen"),
        rx.el.span(CheckboxCardsState.bound.to_string(), id="bound-value"),
        rx.el.span(CheckboxCardsState.submitted.to_string(), id="submitted"),
        rx.el.span(CheckboxCardsState.submissions.to_string(), id="submissions"),
    ),
)

# The text of the checked cards of a group, by the id of its frame.
CHECKED = (
    "id => [...document.getElementById(id).querySelectorAll('label')]"
    ".filter(label => label.querySelector(':checked, [aria-checked=true]'))"
    ".map(label => label.textContent)"
)
# The text of the card that has the focus.
FOCUSED_CARD = "document.activeElement.closest('label')?.textContent"
# How long a step that one system is known not to pass waits, in milliseconds.
QUICK = 3000


def _wait_for_checked(run: Run, group: str, cards: list[str]) -> None:
    """Wait until the checked cards of a group are the ones expected.

    Args:
        run: The run, on a page.
        group: The id of the frame of the group.
        cards: The text of each card that is to be checked.
    """
    run.page.wait_for_function(
        f"([id, cards]) => ({CHECKED})(id).join() === cards",
        arg=[group, ",".join(cards)],
    )


@CONTRACT.step("its cards are in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    assert run.server.element("pick").text == "OneTwoThree"
    assert run.server.element("colors").text == "RedGreenBlue"


@CONTRACT.step("checks its cards with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    page = run.page
    page.set_default_timeout(QUICK)
    page.locator("#pick").get_by_text("Two").click()
    page.locator("#pick").get_by_text("Three").click()
    _wait_for_checked(run, "pick", ["Two", "Three"])
    _wait_for_checked(run, "colors", ["Red"])
    _wait_for_checked(run, "form", ["m"])


@CONTRACT.step("has the roles, the names and the states of a group of checkboxes")
def _role(run: Run) -> None:
    page = run.page
    assert page.get_by_role("group").count() == 5
    pick = page.locator("#pick")
    assert pick.get_by_role("checkbox").count() == 3
    assert not pick.get_by_role("checkbox", name="One").is_checked()
    colors = page.locator("#colors")
    assert colors.get_by_role("checkbox", name="Red", checked=True).count() == 1
    assert colors.get_by_role("checkbox", name="Green", disabled=True).count() == 1
    assert page.locator("#off").get_by_role("checkbox", disabled=True).count() == 2


@CONTRACT.step("Tab stops once in each group")
def _tab(run: Run) -> None:
    page = run.page
    page.set_default_timeout(QUICK)
    stops = []
    for _ in range(4):
        page.keyboard.press("Tab")
        stops.append(page.evaluate(FOCUSED_CARD) or focused(page))
    assert stops == ["One", "Red", "a", "last"]


@CONTRACT.step("the arrow keys move through a group")
def _arrows(run: Run) -> None:
    page = run.page
    page.set_default_timeout(QUICK)
    page.keyboard.press("Tab")
    for key, card in (
        ("ArrowDown", "Two"),
        ("ArrowRight", "Three"),
        ("ArrowUp", "Two"),
    ):
        page.keyboard.press(key, delay=60)
        page.wait_for_function(f"{FOCUSED_CARD} === '{card}'")
    _wait_for_checked(run, "pick", [])


@CONTRACT.step("Tab reaches every card that is not disabled")
def _tab_each(run: Run) -> None:
    page = run.page
    stops = []
    for _ in range(6):
        page.keyboard.press("Tab")
        stops.append(page.evaluate(FOCUSED_CARD) or focused(page))
    assert stops == ["One", "Two", "Three", "Red", "Blue", "a"]


@CONTRACT.step("Space and a click check and uncheck a card, and say so")
def _check(run: Run) -> None:
    page = run.page
    page.locator("#pick").get_by_text("Three").click()
    _wait_for_checked(run, "pick", ["Three"])
    page.keyboard.press("Space")
    _wait_for_checked(run, "pick", [])
    page.locator("#pick").get_by_text("One").click()
    _wait_for_checked(run, "pick", ["One"])
    wait_for_text(page, "seen", '[["Three"],[],["One"]]')


@CONTRACT.step("hands over the checked values in the order they were checked in")
def _order(run: Run) -> None:
    page = run.page
    page.set_default_timeout(QUICK)
    page.locator("#pick").get_by_text("Three").click()
    page.locator("#pick").get_by_text("One").click()
    wait_for_text(page, "seen", '[["Three"],["Three","One"]]')


@CONTRACT.step("a disabled group and a disabled card are not checked")
def _disabled(run: Run) -> None:
    page = run.page
    page.locator("#off").get_by_text("x").click(force=True)
    page.locator("#colors").get_by_text("Green").click(force=True)
    page.locator("#colors").get_by_text("Blue").click()
    _wait_for_checked(run, "colors", ["Red", "Blue"])
    _wait_for_checked(run, "off", [])


@CONTRACT.step("follows the state it is bound to")
def _bound(run: Run) -> None:
    page = run.page
    _wait_for_checked(run, "bound", ["a"])
    page.locator("#bound").get_by_text("b").click()
    wait_for_text(page, "bound-value", '["a","b"]')
    _wait_for_checked(run, "bound", ["a", "b"])
    page.locator("#last").click()
    wait_for_text(page, "bound-value", '["c"]')
    _wait_for_checked(run, "bound", ["c"])


@CONTRACT.step("submits with a form")
def _submit(run: Run) -> None:
    page = run.page
    page.locator("#form").get_by_text("l").click()
    page.locator("#send").click()
    wait_for_text(page, "submissions", "1")
    # A form of Reflex keeps one value of each name: the last one.
    assert page.locator("#submitted").text_content() == '{"size":"l"}'
