"""The text field: every variant, size and state, its slots, and what it does with text."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.look import FOCUS_WITHIN
from ui_parity.matrix import DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import ACCENTS, focused, wait_for_text

VARIANTS = ["classic", "surface", "soft"]
SIZES = ["1", "2", "3"]
RADII = ["none", "small", "medium", "large", "full"]
STATES = ["rest", HOVER, FOCUS_VISIBLE]
HOLDS = ["icon", "end", "both", "two", "button", "color"]


def _field(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a text field, with the slots a cell says it holds.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``holds`` names its slots.

    Returns:
        The text field.
    """
    props = dict(props)
    holds = props.pop("holds", None)
    slot = namespace.input.slot
    slots: list[Any] = []
    if holds == "icon":
        slots = [slot(rx.icon("search", size=16))]
    elif holds == "end":
        slots = [slot("kg", side="right")]
    elif holds == "both":
        slots = [
            slot(rx.icon("search", size=16), side="left"),
            slot("kg", side="right"),
        ]
    elif holds == "two":
        slots = [slot(rx.icon("search", size=16)), slot("kg")]
    elif holds == "button":
        slots = [
            slot(
                namespace.icon_button(rx.icon("x", size=14), size="1", variant="ghost"),
                side="right",
            )
        ]
    elif holds == "color":
        slots = [slot(rx.icon("search", size=16), color_scheme="ruby")]
    return namespace.input(*slots, **props)


MATRIX = Matrix(
    component="text_field",
    render=_field,
    base={"placeholder": "Search"},
    cross={"variant": VARIANTS, "size": SIZES, "holds": [None, "both"]},
    sweep={
        "color_scheme": ACCENTS,
        "radius": RADII,
        "disabled": [True],
        "read_only": [True],
        "default_value": ["Hello"],
        "type": ["password", "number", "search", "email", "date", "time"],
        "holds": HOLDS,
        "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
        "appearance": [DARK],
        "state": STATES,
        "viewport": [520],
    },
    groups=[
        {
            "variant": VARIANTS,
            "default_value": ["Hello"],
            "disabled": [False, True],
            "read_only": [False, True],
            "appearance": [LIGHT, DARK],
        },
        {
            "variant": VARIANTS,
            "disabled": [True],
            "appearance": [LIGHT, DARK],
        },
        {
            "variant": VARIANTS,
            "color_scheme": ["ruby", "gray", "yellow"],
            "state": STATES,
            "default_value": ["Hello"],
        },
        {"variant": VARIANTS, "state": STATES, "appearance": [LIGHT, DARK]},
        {"variant": VARIANTS, "holds": HOLDS, "size": ["1", "3"]},
        {"variant": VARIANTS, "holds": ["both"], "disabled": [True]},
        {"radius": RADII, "size": SIZES, "holds": [None, "both"]},
        {
            "type": ["password", "date", "time"],
            "default_value": {"filled": "2024-05-06"},
            "holds": [None, "icon"],
        },
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
            "viewport": [520, 800, 1100],
        },
    ],
    stage=(260, 80),
    parts={"input": "input"},
    # The focus is on the input inside the box.
    states={FOCUS_VISIBLE: FOCUS_WITHIN},
    # Not held to zero. At a threshold of zero 199 of the 217 cells are equal
    # pixel for pixel, and the others differ by where they are on the page:
    # the fill of a disabled or read-only field is a gradient, which is
    # dithered by a step of a channel, and the corners of the larger radii
    # are anti-aliased otherwise. At the default threshold 2 cells differ, by
    # 2 pixels of 11712 on a corner of the full radius.
    tolerance=0.0002,
)


class TextFieldState(rx.State):
    """What the text fields of the contract are bound to."""

    bound: rx.Field[str] = rx.field("start")
    seen: rx.Field[list[str]] = rx.field(default_factory=list)
    keys: rx.Field[list[str]] = rx.field(default_factory=list)
    submitted: rx.Field[dict[str, Any]] = rx.field(default_factory=dict)
    submissions: rx.Field[int] = rx.field(0)

    @rx.event
    def set_bound(self, value: str):
        """Follow the bound field.

        Args:
            value: Its text.
        """
        self.bound = value

    @rx.event
    def see(self, value: str):
        """Keep what an event handed over.

        Args:
            value: The text of the field.
        """
        self.seen.append(value)

    @rx.event
    def see_key(self, key: str):
        """Keep the key an event handed over.

        Args:
            key: The key.
        """
        self.keys.append(key)

    @rx.event
    def reset_bound(self):
        """Change the bound value from outside the field."""
        self.bound = "reset"

    @rx.event
    def submit(self, data: dict[str, Any]):
        """Keep what a form submitted.

        Args:
            data: The values of the form.
        """
        self.submitted = data
        self.submissions += 1


CONTRACT = Contract(
    component="text_field",
    render=lambda namespace: namespace.box(
        rx.el.label("Name", html_for="name"),
        namespace.input(
            id="name",
            placeholder="Your name",
            on_change=TextFieldState.see,
            on_key_down=TextFieldState.see_key,
        ),
        namespace.input(id="off", disabled=True, default_value="off"),
        namespace.input(id="fixed", read_only=True, default_value="fixed"),
        namespace.input(
            id="events",
            aria_label="Events",
            on_focus=TextFieldState.see,
            on_blur=TextFieldState.see,
            default_value="e",
        ),
        namespace.input(
            id="bound",
            aria_label="Bound",
            value=TextFieldState.bound,
            on_change=TextFieldState.set_bound,
        ),
        rx.el.button("Reset", id="reset", on_click=TextFieldState.reset_bound),
        rx.el.button("Set", id="set", on_click=rx.set_value("name", "set")),
        rx.el.button("Focus", id="focus", on_click=rx.set_focus("name")),
        rx.el.div(
            namespace.input(
                namespace.input.slot(rx.icon("search", size=16), id="left-slot"),
                namespace.input.slot("kg", side="right", id="right-slot"),
                namespace.input.slot(
                    rx.el.button("Clear", id="clear", type="button"), side="right"
                ),
                id="slotted",
                aria_label="Slotted",
                default_value="abcdef",
            ),
            id="slots",
            style={"width": "300px"},
        ),
        rx.el.div(namespace.input(id="hidden", type="hidden", name="h"), id="gone"),
        rx.el.form(
            namespace.input(id="q", name="q", required=True, max_length=4),
            namespace.input(id="n", name="n", type="number", default_value="7"),
            rx.el.button("Send", id="send", type="submit"),
            on_submit=TextFieldState.submit,
            id="form",
        ),
        rx.el.span(TextFieldState.seen.to_string(), id="seen"),
        rx.el.span(TextFieldState.keys.to_string(), id="keys"),
        rx.el.span(TextFieldState.bound, id="bound-value"),
        rx.el.span(TextFieldState.submitted.to_string(), id="submitted"),
        rx.el.span(TextFieldState.submissions.to_string(), id="submissions"),
    ),
)


@CONTRACT.step("is an input with its attributes in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    name = run.server.element("name")
    assert (name.tag, name.attributes["placeholder"]) == ("input", "Your name")
    assert run.server.element("off").attributes["value"] == "off"
    assert "disabled" in run.server.element("off").attributes
    assert "readonly" in run.server.element("fixed").attributes
    assert run.server.element("bound").attributes["value"] == "start"


@CONTRACT.step("takes the focus and text with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    page = run.page
    page.get_by_text("Name", exact=True).click()
    assert focused(page) == "name"
    page.keyboard.type("Ada")
    assert page.locator("#name").input_value() == "Ada"


@CONTRACT.step("has the role and the name of a text box, and its label")
def _role(run: Run) -> None:
    page = run.page
    assert page.get_by_role("textbox", name="Name").get_attribute("id") == "name"
    assert page.get_by_label("Name", exact=True).get_attribute("id") == "name"
    assert page.get_by_role("textbox", name="Events").get_attribute("id") == "events"
    assert page.get_by_role("textbox", disabled=True).count() == 1
    assert page.get_by_role("spinbutton").get_attribute("id") == "n"


@CONTRACT.step("Tab stops on each field but a disabled one")
def _tab(run: Run) -> None:
    stops = []
    for _ in range(4):
        run.page.keyboard.press("Tab")
        stops.append(focused(run.page))
    assert stops == ["name", "fixed", "events", "bound"]


@CONTRACT.step("typing changes the text and says so, key by key")
def _type(run: Run) -> None:
    page = run.page
    page.locator("#name").focus()
    page.keyboard.type("Ada", delay=30)
    assert page.locator("#name").input_value() == "Ada"
    wait_for_text(page, "seen", '["A","Ad","Ada"]')
    wait_for_text(page, "keys", '["A","d","a"]')


@CONTRACT.step("focus and blur hand over the text")
def _focus_blur(run: Run) -> None:
    page = run.page
    page.locator("#events").focus()
    wait_for_text(page, "seen", '["e"]')
    page.keyboard.press("End")
    page.keyboard.type("x")
    page.keyboard.press("Tab")
    wait_for_text(page, "seen", '["e","ex"]')


@CONTRACT.step("a disabled field takes no text, and a read-only one the focus alone")
def _disabled(run: Run) -> None:
    page = run.page
    assert page.locator("#off").is_disabled()
    page.locator("#fixed").focus()
    page.keyboard.type("x")
    assert page.locator("#fixed").input_value() == "fixed"
    assert focused(page) == "fixed"


@CONTRACT.step("a field bound to state keeps what is typed and follows the state")
def _bound(run: Run) -> None:
    page = run.page
    bound = page.locator("#bound")
    assert bound.input_value() == "start"
    bound.focus()
    page.keyboard.press("End")
    page.keyboard.type(" and more", delay=15)
    assert bound.input_value() == "start and more"
    wait_for_text(page, "bound-value", "start and more")
    assert bound.input_value() == "start and more"
    page.locator("#reset").click()
    wait_for_text(page, "bound-value", "reset")
    page.wait_for_function("document.getElementById('bound').value === 'reset'")


@CONTRACT.step("rx.set_value and rx.set_focus reach the input by its id")
def _refs(run: Run) -> None:
    page = run.page
    page.locator("#set").click()
    page.wait_for_function("document.getElementById('name').value === 'set'")
    page.locator("#focus").click()
    page.wait_for_function("document.activeElement.id === 'name'")


@CONTRACT.step("a pointer on a slot gives the input the focus, at that end of its text")
def _slots(run: Run) -> None:
    page = run.page
    caret = "[document.activeElement.id, document.activeElement.selectionStart]"
    page.locator("#right-slot").click()
    page.wait_for_function(f"{caret}.join() === 'slotted,6'")
    page.locator("#name").focus()
    page.locator("#left-slot").click()
    page.wait_for_function(f"{caret}.join() === 'slotted,0'")
    page.locator("#name").focus()
    page.locator("#clear").click()
    page.wait_for_timeout(100)
    assert focused(page) == "clear"


@CONTRACT.step("a hidden input leaves no box behind")
def _hidden(run: Run) -> None:
    page = run.page
    assert page.locator("#gone").bounding_box() == {
        **(page.locator("#gone").bounding_box() or {}),
        "height": 0,
    }
    assert page.locator("#hidden").get_attribute("type") == "hidden"


@CONTRACT.step("submits its text with a form, as its type has it")
def _submit(run: Run) -> None:
    page = run.page
    page.locator("#q").focus()
    page.keyboard.type("abcdefg")
    assert page.locator("#q").input_value() == "abcd"
    page.keyboard.press("Enter")
    wait_for_text(page, "submissions", "1")
    assert page.locator("#submitted").text_content() == '{"q":"abcd","n":"7"}'


@CONTRACT.step("a required field holds its form back until it has text")
def _required(run: Run) -> None:
    page = run.page
    page.locator("#send").click()
    # An event that does reach the server comes back after the blocked one.
    page.locator("#reset").click()
    wait_for_text(page, "bound-value", "reset")
    assert page.locator("#submissions").text_content() == "0"
    page.locator("#q").fill("ok")
    page.locator("#send").click()
    wait_for_text(page, "submissions", "1")
