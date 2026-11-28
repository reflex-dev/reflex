"""The accordion: every variant, closed, open and with several items, and its keys."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from playwright.sync_api import Locator, Page

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.look import Point, State
from ui_parity.matrix import DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import wait_for_text

VARIANTS = ["classic", "soft", "surface", "outline", "ghost"]
RADII = ["none", "small", "full"]
STATES = [HOVER, FOCUS_VISIBLE]
NAMES = ("First", "Second", "Third")


def _accordion(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create an accordion of three items.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the root. ``item_variant`` and ``item_color``
            are the variant and the color of the second item, ``disabled``
            says that the last item is, and ``parts`` asks for items made
            of their parts, with a header of two lines.

    Returns:
        The accordion.
    """
    props = dict(props)
    accordion = namespace.accordion
    second = {
        prop: props.pop(key)
        for key, prop in (("item_variant", "variant"), ("item_color", "color_scheme"))
        if key in props
    }
    disabled = props.pop("disabled", False)
    if props.pop("parts", False):
        items = [
            accordion.item(
                accordion.header(
                    accordion.trigger(
                        rx.el.span(f"{name} item, with a header long enough for two"),
                        accordion.icon(),
                    )
                ),
                accordion.content(rx.el.p(f"What the {name.lower()} item holds.")),
                value=name.lower(),
            )
            for name in NAMES
        ]
    else:
        items = [
            accordion.item(
                header=name,
                content=f"What the {name.lower()} item holds.",
                value=name.lower(),
                **(second if name == "Second" else {}),
                **({"disabled": True} if disabled and name == "Third" else {}),
            )
            for name in NAMES
        ]
    return accordion.root(*items, **props)


def _focus(page: Page, target: Locator, point: Point) -> None:
    """Focus the header of an item as the keyboard does.

    Args:
        page: The page.
        target: The trigger: a button of Radix, the heading in a summary here.
        point: The middle of the trigger.
    """
    page.keyboard.press("Tab")
    target.evaluate("element => (element.closest('summary') ?? element).focus()")


def _blur(page: Page, target: Locator, point: Point) -> None:
    """Take the focus off whatever has it.

    Args:
        page: The page.
        target: The trigger.
        point: The middle of the trigger.
    """
    page.evaluate("document.activeElement.blur()")


MATRIX = Matrix(
    component="accordion",
    render=_accordion,
    base={"default_value": "second", "collapsible": True},
    cross={"variant": VARIANTS, "default_value": {"second": "second", "none": None}},
    sweep={
        "color_scheme": ["ruby", "gray", "yellow", "indigo"],
        "radius": RADII,
        "show_dividers": [True, False],
        "disabled": [True],
        "parts": [True],
        "type": ["multiple"],
        "item_variant": VARIANTS,
        "item_color": ["ruby"],
        "appearance": [DARK],
        "state": STATES,
    },
    groups=[
        {"variant": VARIANTS, "state": STATES, "appearance": [LIGHT, DARK]},
        {"variant": VARIANTS, "show_dividers": [True, False]},
        {"variant": VARIANTS, "color_scheme": ["ruby", "gray"], "appearance": [DARK]},
        {"variant": ["soft", "ghost"], "item_variant": ["classic", "ghost", "outline"]},
        {"variant": VARIANTS, "radius": ["none", "full"]},
        {
            "type": ["multiple"],
            "default_value": {"all": ["first", "second", "third"], "first": ["first"]},
        },
        {"default_value": {"first": "first", "third": "third"}, "variant": VARIANTS},
        {"disabled": [True], "state": STATES},
        {"parts": [True], "variant": ["classic", "outline"], "state": STATES},
    ],
    stage=(360, 300),
    crop="stage",
    target=".AccordionItem:nth-of-type(1) .AccordionTrigger",
    parts={
        "root": ":scope > div",
        "item": ".AccordionItem:nth-of-type(1)",
        "middle": ".AccordionItem:nth-of-type(2)",
        "last": ".AccordionItem:nth-of-type(3)",
        "header": ".AccordionItem:nth-of-type(1) .AccordionHeader",
        "icon": ".AccordionItem:nth-of-type(1) .AccordionChevron",
        "second": ".AccordionItem:nth-of-type(2) .AccordionTrigger",
        "third": ".AccordionItem:nth-of-type(3) .AccordionTrigger",
    },
    # The focus is on the button of Radix, and on the summary around the
    # heading here.
    states={
        FOCUS_VISIBLE: State(
            enter=_focus,
            leave=_blur,
            matches=":is(:focus-visible, summary:focus-visible *)",
        )
    },
    # Not held to zero. At a threshold of zero 87 of the 106 cells are equal
    # pixel for pixel, and the others differ by at most 5 pixels of 108000
    # on a rounded corner, which the browser anti-aliases by where the
    # accordion is on the page: the accordion of Radix differs from itself by
    # as much between two frames of the same look. At the default threshold
    # 3 cells differ, by 2 pixels.
    tolerance=0.00005,
)


class AccordionState(rx.State):
    """What the accordions of the contract are bound to."""

    bound: rx.Field[str] = rx.field("b")
    seen: rx.Field[list[str]] = rx.field(default_factory=list)

    @rx.event
    def set_bound(self, value: str | list[str]):
        """Follow the bound accordion.

        Args:
            value: The value of its open item.
        """
        self.bound = str(value)

    @rx.event
    def see(self, value: str | list[str]):
        """Keep what a change handed over.

        Args:
            value: The value of the open item, or of each open item.
        """
        self.seen.append(json.dumps(value))

    @rx.event
    def pick_last(self):
        """Change the bound value from outside the accordion."""
        self.bound = "c"


def _letters(namespace: Any, name: str, off: str = "", **props: Any) -> Any:
    """Create an accordion of three items named by a letter, in a frame.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        name: The id of the frame.
        off: The letter of a disabled item.
        **props: The props of the root.

    Returns:
        The frame.
    """
    accordion = namespace.accordion
    return rx.el.div(
        accordion.root(
            *(
                accordion.item(
                    header=f"Header {letter}",
                    content=f"Panel {letter}",
                    value=letter,
                    **({"disabled": True} if letter == off else {}),
                )
                for letter in "abc"
            ),
            **props,
        ),
        id=name,
    )


CONTRACT = Contract(
    component="accordion",
    render=lambda namespace: namespace.box(
        namespace.accordion.root(
            namespace.accordion.item(
                namespace.accordion.header(
                    namespace.accordion.trigger("Made", id="made-header")
                ),
                namespace.accordion.content("Of its parts", id="made-panel"),
                value="made",
            ),
            default_value="made",
        ),
        _letters(
            namespace, "plain", default_value="a", on_value_change=AccordionState.see
        ),
        _letters(
            namespace,
            "folds",
            default_value="a",
            collapsible=True,
            on_value_change=AccordionState.see,
        ),
        _letters(
            namespace,
            "several",
            type="multiple",
            default_value=["b"],
            on_value_change=AccordionState.see,
        ),
        _letters(namespace, "free", type="multiple"),
        _letters(
            namespace,
            "bound",
            value=AccordionState.bound,
            on_value_change=AccordionState.set_bound,
        ),
        _letters(namespace, "partly", off="b", collapsible=True),
        rx.el.button("Last", id="last", on_click=AccordionState.pick_last),
        rx.el.span(AccordionState.seen.to_string(), id="seen"),
        rx.el.span(AccordionState.bound, id="bound-value"),
    ),
)

# The text of the panels of an accordion that are shown, by the id of its frame.
OPEN = (
    "id => [...document.getElementById(id).querySelectorAll('.AccordionContent')]"
    ".filter(panel => panel.checkVisibility({contentVisibilityAuto: true}))"
    ".map(panel => panel.textContent)"
)
# How long a panel takes to open or close, and some more, in milliseconds.
STILL = 400
# What takes the focus in a header: the button of Radix, the summary here.
HEADER = "button.AccordionTrigger, summary"
# The text of the header that has the focus, or the id of anything else.
FOCUSED = (
    "document.activeElement.matches('button.AccordionTrigger, summary')"
    " ? document.activeElement.textContent : document.activeElement.id"
)


def _wait_for_open(run: Run, name: str, *letters: str) -> None:
    """Wait until the open items of an accordion are the ones expected.

    Args:
        run: The run, on a page.
        name: The id of the frame of the accordion.
        *letters: The letter of each item that is to be open.
    """
    run.page.wait_for_function(
        f"([id, panels]) => JSON.stringify(({OPEN})(id)) === panels",
        arg=[
            name,
            json.dumps(
                [f"Panel {letter}" for letter in letters], separators=(",", ":")
            ),
        ],
    )


def _header(run: Run, name: str, letter: str) -> Locator:
    """Find the header of an item.

    Args:
        run: The run, on a page.
        name: The id of the frame of the accordion.
        letter: The letter of the item.

    Returns:
        What takes the focus in the header.
    """
    return (
        run.page.locator(f"#{name}").locator(HEADER).filter(has_text=f"Header {letter}")
    )


@CONTRACT.step("the panel of the open item is in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    assert run.server.element("made-header").text == "Made"
    assert run.server.element("made-panel").text == "Of its parts"


@CONTRACT.step("opens and closes an item with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    page = run.page
    page.set_default_timeout(3000)

    def press(name: str, letter: str) -> list[str]:
        # With scripts off the page is read once its panels are still:
        # nothing in it polls for them.
        _header(run, name, letter).click()
        page.wait_for_timeout(STILL)
        return page.evaluate(f"({OPEN})('{name}')")

    assert page.evaluate(f"({OPEN})('plain')") == ["Panel a"]
    assert press("plain", "b") == ["Panel b"]
    assert press("free", "c") == ["Panel c"]
    assert press("free", "a") == ["Panel a", "Panel c"]
    assert press("free", "c") == ["Panel a"]


@CONTRACT.step("a header is a heading, and says whether its item is open")
def _role(run: Run) -> None:
    page = run.page
    plain = page.locator("#plain")
    assert plain.get_by_role("heading", level=3).all_text_contents() == [
        "Header a",
        "Header b",
        "Header c",
    ]
    # An open item says so on its button in Radix, and as a `details` here.
    said = plain.locator("button[aria-expanded=true], details[open] > summary")
    assert said.all_text_contents() == ["Header a"]
    assert plain.get_by_role("region", name="Header a").text_content() == "Panel a"


@CONTRACT.step("Enter and Space open and close an item")
def _keys(run: Run) -> None:
    page = run.page
    _header(run, "folds", "b").focus()
    page.keyboard.press("Enter")
    _wait_for_open(run, "folds", "b")
    page.keyboard.press("Space")
    _wait_for_open(run, "folds")
    page.keyboard.press("Space")
    _wait_for_open(run, "folds", "b")
    page.keyboard.press("Enter")
    _wait_for_open(run, "folds")


@CONTRACT.step("Tab stops on every header, and not on a disabled one")
def _tab(run: Run) -> None:
    page = run.page
    page.locator("#last").focus()
    stops = []
    for _ in range(3):
        page.keyboard.press("Shift+Tab")
        stops.append(page.evaluate(FOCUSED))
    assert stops == ["Header c", "Header a", "Header c"]
    _header(run, "partly", "b").click(force=True)
    page.wait_for_timeout(300)
    _wait_for_open(run, "partly")


@CONTRACT.step("one item is open at a time, and the open one stays open")
def _single(run: Run) -> None:
    page = run.page
    _wait_for_open(run, "plain", "a")
    _header(run, "plain", "a").click(force=True)
    page.wait_for_timeout(400)
    _wait_for_open(run, "plain", "a")
    _header(run, "plain", "c").click()
    _wait_for_open(run, "plain", "c")
    _header(run, "plain", "c").focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(400)
    _wait_for_open(run, "plain", "c")
    wait_for_text(page, "seen", '["\\"c\\""]')


@CONTRACT.step("a collapsible accordion closes its open item, and says so")
def _collapsible(run: Run) -> None:
    page = run.page
    _header(run, "folds", "a").click()
    _wait_for_open(run, "folds")
    _header(run, "folds", "b").click()
    _wait_for_open(run, "folds", "b")
    wait_for_text(page, "seen", '["\\"\\"","\\"b\\""]')


@CONTRACT.step("an accordion of several opens each item by itself, and says which")
def _multiple(run: Run) -> None:
    page = run.page
    _wait_for_open(run, "several", "b")
    _header(run, "several", "c").click()
    _wait_for_open(run, "several", "b", "c")
    _header(run, "several", "b").click()
    _wait_for_open(run, "several", "c")
    wait_for_text(page, "seen", '["[\\"b\\", \\"c\\"]","[\\"c\\"]"]')


@CONTRACT.step("hands over the open items in the order they were opened in")
def _order(run: Run) -> None:
    page = run.page
    _header(run, "several", "a").click()
    _wait_for_open(run, "several", "a", "b")
    wait_for_text(page, "seen", '["[\\"b\\", \\"a\\"]"]')


@CONTRACT.step("an accordion bound to state shows the item of the state")
def _bound(run: Run) -> None:
    page = run.page
    _wait_for_open(run, "bound", "b")
    _header(run, "bound", "a").click()
    wait_for_text(page, "bound-value", "a")
    _wait_for_open(run, "bound", "a")
    page.locator("#last").click()
    wait_for_text(page, "bound-value", "c")
    _wait_for_open(run, "bound", "c")


@CONTRACT.step("the arrow keys, Home and End move between the headers")
def _arrows(run: Run) -> None:
    page = run.page
    _header(run, "plain", "a").focus()
    for key, letter in (
        ("ArrowDown", "b"),
        ("End", "c"),
        ("ArrowUp", "b"),
        ("Home", "a"),
    ):
        page.keyboard.press(key)
        page.wait_for_function(
            f"header => ({FOCUSED}) === header", arg=f"Header {letter}"
        )
