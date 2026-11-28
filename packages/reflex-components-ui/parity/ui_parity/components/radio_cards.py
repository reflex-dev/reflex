"""Radio cards: every variant, size and state, and what native radio buttons give them."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.look import FOCUS_WITHIN
from ui_parity.matrix import ACTIVE, DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import ACCENTS, focused, wait_for_text, wait_for_value

VARIANTS = ["surface", "classic"]
SIZES = ["1", "2", "3"]
STATES = ["rest", HOVER, FOCUS_VISIBLE, ACTIVE]
# The first card: a button of Radix, a label here.
TARGET = ("button", "label")


def _cards(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create radio cards.

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
    return namespace.radio_cards.root(
        namespace.radio_cards.item(*first, value="1"),
        namespace.radio_cards.item("Two", value="2"),
        namespace.radio_cards.item("Three", value="3", disabled=True),
        **props,
    )


MATRIX = Matrix(
    component="radio_cards",
    render=_cards,
    base={"default_value": "1", "columns": "3", "gap": "2"},
    cross={"variant": VARIANTS, "size": SIZES, "default_value": ["1", "2"]},
    sweep={
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
        {"variant": VARIANTS, "disabled": [True], "appearance": [LIGHT, DARK]},
        {
            "variant": VARIANTS,
            "default_value": ["1", "2"],
            "state": STATES,
            "appearance": [LIGHT, DARK],
        },
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
            "viewport": [520, 800, 1100],
        },
    ],
    stage=(360, 150),
    crop="stage",
    target=TARGET,
    # The focus is on the card of Radix and on the input in the card here.
    states={FOCUS_VISIBLE: FOCUS_WITHIN},
    # Not held to zero. The translucent fill of a card, its rounded clip and
    # the layers of its border are dithered and anti-aliased by where the
    # card is on the page: with the two frames of a cell swapped, each system
    # is equal pixel for pixel to the other one in the same place. At the
    # default threshold 32 of the 99 cells differ, by at most 10 pixels of
    # 54000.
    tolerance=0.0005,
)


class RadioCardsState(rx.State):
    """What the radio cards of the contract are bound to."""

    bound: rx.Field[str] = rx.field("a")
    seen: rx.Field[list[str]] = rx.field(default_factory=list)
    submitted: rx.Field[dict[str, str]] = rx.field(default_factory=dict)
    submissions: rx.Field[int] = rx.field(0)

    @rx.event
    def set_bound(self, value: str):
        """Follow the bound group.

        Args:
            value: The value of its checked card.
        """
        self.bound = value

    @rx.event
    def see(self, value: str):
        """Keep what a change handed over.

        Args:
            value: The value of the checked card.
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


def _items(namespace: Any, *values: str) -> list[Any]:
    """Create the cards of a group, each with its value as its text.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        *values: The value of each card.

    Returns:
        The cards.
    """
    return [namespace.radio_cards.item(value, value=value) for value in values]


CONTRACT = Contract(
    component="radio_cards",
    render=lambda namespace: namespace.box(
        rx.el.div(
            namespace.radio_cards.root(
                *_items(namespace, "One", "Two", "Three"),
                on_value_change=RadioCardsState.see,
            ),
            id="pick",
        ),
        rx.el.div(
            namespace.radio_cards.root(
                namespace.radio_cards.item("Red", value="red"),
                namespace.radio_cards.item("Green", value="green", disabled=True),
                namespace.radio_cards.item("Blue", value="blue"),
                default_value="red",
            ),
            id="colors",
        ),
        rx.el.div(
            namespace.radio_cards.root(
                *_items(namespace, "a", "b", "c"),
                value=RadioCardsState.bound,
                on_value_change=RadioCardsState.set_bound,
            ),
            id="bound",
        ),
        rx.el.button("Last", id="last", on_click=RadioCardsState.pick_last),
        rx.el.div(
            namespace.radio_cards.root(*_items(namespace, "x", "y"), disabled=True),
            id="off",
        ),
        rx.el.form(
            namespace.radio_cards.root(
                *_items(namespace, "s", "m", "l"), name="size", default_value="m"
            ),
            namespace.radio_cards.root(
                *_items(namespace, "yes", "no"), name="answer", required=True
            ),
            rx.el.button("Send", id="send", type="submit"),
            on_submit=RadioCardsState.submit,
            id="form",
        ),
        rx.el.span(RadioCardsState.seen.to_string(), id="seen"),
        rx.el.span(RadioCardsState.bound, id="bound-value"),
        rx.el.span(RadioCardsState.submitted.to_string(), id="submitted"),
        rx.el.span(RadioCardsState.submissions.to_string(), id="submissions"),
    ),
)

# A card is a button of Radix and a label around an input here.
CARDS = "button[role=radio], label"
# The text of the checked cards of a group, by the id of its frame.
CHECKED = (
    f"id => [...document.getElementById(id).querySelectorAll('{CARDS}')]"
    ".filter(card => card.matches('[aria-checked=true], :has(:checked)'))"
    ".map(card => card.textContent)"
)
# The text of the card that has the focus.
FOCUSED_CARD = f"(document.activeElement.closest('{CARDS}')?.textContent ?? null)"
# How long a key is held, in milliseconds.
HELD = 60


def _wait_for_checked(run: Run, group: str, cards: list[str]) -> None:
    """Wait until the checked cards of a group are the ones expected.

    Args:
        run: The run, on a page.
        group: The id of the frame of the group.
        cards: The text of each card that is to be checked.
    """
    wait_for_value(run.page, f"({CHECKED})({json.dumps(group)})", cards)


def _wait_for_focus(run: Run, card: str) -> None:
    """Wait until a card has the focus.

    Args:
        run: The run, on a page.
        card: The text of the card.
    """
    wait_for_value(run.page, FOCUSED_CARD, card)


@CONTRACT.step("its cards are in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    assert run.server.element("pick").text == "OneTwoThree"
    assert run.server.element("colors").text == "RedGreenBlue"


@CONTRACT.step("checks one card of a group with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    page = run.page
    page.set_default_timeout(3000)
    page.locator("#pick").get_by_text("Two").click()
    _wait_for_checked(run, "pick", ["Two"])
    page.locator("#pick").get_by_text("Three").click()
    _wait_for_checked(run, "pick", ["Three"])
    _wait_for_checked(run, "colors", ["Red"])


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


@CONTRACT.step("Tab stops once in each group, on its checked card")
def _tab(run: Run) -> None:
    page = run.page
    stops = []
    for _ in range(4):
        page.keyboard.press("Tab")
        stops.append(page.evaluate(FOCUSED_CARD) or focused(page))
    assert stops == ["One", "Red", "a", "last"]
    _wait_for_checked(run, "pick", [])


@CONTRACT.step("the arrow keys move through a group and check, past a disabled card")
def _arrows(run: Run) -> None:
    page = run.page
    page.keyboard.press("Tab")
    for key, card in (
        ("ArrowDown", "Two"),
        ("ArrowRight", "Three"),
        ("ArrowUp", "Two"),
        ("ArrowLeft", "One"),
    ):
        # Held as long as a finger holds it: Radix checks the card the focus
        # moves to only while the key is still down.
        page.keyboard.press(key, delay=HELD)
        _wait_for_focus(run, card)
        _wait_for_checked(run, "pick", [card])
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


@CONTRACT.step("Space and a click check a card, and say so")
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


@CONTRACT.step("Enter on a card does not submit its form")
def _enter_in_form(run: Run) -> None:
    page = run.page
    page.locator("#form").get_by_text("yes").click()
    page.keyboard.press("Enter")
    page.locator("#last").click()
    wait_for_text(page, "bound-value", "c")
    assert page.locator("#submissions").text_content() == "0"


@CONTRACT.step("a disabled group and a disabled card are not checked")
def _disabled(run: Run) -> None:
    page = run.page
    page.locator("#off").get_by_text("x").click(force=True)
    page.locator("#colors").get_by_text("Green").click(force=True)
    page.locator("#pick").get_by_text("Two").click()
    _wait_for_checked(run, "pick", ["Two"])
    _wait_for_checked(run, "off", [])
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


@CONTRACT.step("submits the value of its checked card with a form")
def _submit(run: Run) -> None:
    page = run.page
    page.locator("#form").get_by_text("no").click()
    page.locator("#send").click()
    wait_for_text(page, "submissions", "1")
    assert page.locator("#submitted").text_content() == '{"size":"m","answer":"no"}'


@CONTRACT.step("a required group holds its form back until a card is checked")
def _required(run: Run) -> None:
    page = run.page
    page.locator("#send").click()
    # An event that does reach the server comes back after the blocked one.
    page.locator("#last").click()
    wait_for_text(page, "bound-value", "c")
    assert page.locator("#submissions").text_content() == "0"
    page.locator("#form").get_by_text("yes").click()
    page.locator("#send").click()
    wait_for_text(page, "submissions", "1")
