"""The text area: every variant, size and state, and what it does with text."""

from __future__ import annotations

from typing import Any

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.look import FOCUS_WITHIN
from ui_parity.matrix import DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import ACCENTS, PARAGRAPH, focused, wait_for_text

VARIANTS = ["classic", "surface", "soft"]
SIZES = ["1", "2", "3"]
RADII = ["none", "small", "medium", "large", "full"]
STATES = ["rest", HOVER, FOCUS_VISIBLE]
RESIZE = ["none", "vertical", "horizontal", "both"]

MATRIX = Matrix(
    component="text_area",
    base={"placeholder": "Say something"},
    cross={"variant": VARIANTS, "size": SIZES},
    sweep={
        "color_scheme": ACCENTS,
        "radius": RADII,
        "disabled": [True],
        "read_only": [True],
        "default_value": {"hello": "Hello", "long": PARAGRAPH * 4},
        "rows": ["2", "6"],
        "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
        "resize": [*RESIZE, rx.breakpoints(initial="none", sm="both")],
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
        {"variant": VARIANTS, "disabled": [True], "appearance": [LIGHT, DARK]},
        {
            "variant": VARIANTS,
            "color_scheme": ["ruby", "gray", "yellow"],
            "state": STATES,
            "default_value": ["Hello"],
        },
        {"variant": VARIANTS, "state": STATES, "appearance": [LIGHT, DARK]},
        {"variant": VARIANTS, "default_value": {"long": PARAGRAPH * 4}},
        {"radius": RADII, "size": SIZES},
        {"resize": RESIZE, "variant": VARIANTS},
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
            "viewport": [520, 800, 1100],
        },
    ],
    stage=(260, 160),
    parts={"textarea": "textarea"},
    # The focus is on the textarea inside the box.
    states={FOCUS_VISIBLE: FOCUS_WITHIN},
    # Every cell is equal at the default threshold. At a threshold of zero
    # 7 of them differ, the disabled and read-only ones: their fill is a
    # gradient, which is dithered by a step of a channel by where the text
    # area is on the page.
    tolerance=0,
)


class TextAreaState(rx.State):
    """What the text areas of the contract are bound to."""

    bound: str = "start"
    seen: list[str] = []
    submitted: dict[str, Any] = {}
    submissions: int = 0

    @rx.event
    def set_bound(self, value: str):
        """Follow the bound text area.

        Args:
            value: Its text.
        """
        self.bound = value

    @rx.event
    def see(self, value: str):
        """Keep what an event handed over.

        Args:
            value: The text of the text area.
        """
        self.seen.append(value)

    @rx.event
    def reset_bound(self):
        """Change the bound value from outside the text area."""
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
    component="text_area",
    render=lambda namespace: namespace.box(
        rx.el.label("Notes", html_for="notes"),
        namespace.text_area(
            id="notes", placeholder="Your notes", on_change=TextAreaState.see, rows="2"
        ),
        namespace.text_area(id="off", disabled=True, default_value="off"),
        namespace.text_area(id="fixed", read_only=True, default_value="fixed"),
        namespace.text_area(
            id="events",
            aria_label="Events",
            on_focus=TextAreaState.see,
            on_blur=TextAreaState.see,
            default_value="e",
        ),
        namespace.text_area(
            id="bound",
            aria_label="Bound",
            value=TextAreaState.bound,
            on_change=TextAreaState.set_bound,
        ),
        rx.el.button("Reset", id="reset", on_click=TextAreaState.reset_bound),
        rx.el.button("Set", id="set", on_click=rx.set_value("notes", "set")),
        rx.el.button("Focus", id="focus", on_click=rx.set_focus("notes")),
        rx.el.form(
            namespace.text_area(id="q", name="q", required=True, max_length=4),
            rx.el.button("Send", id="send", type="submit"),
            on_submit=TextAreaState.submit,
            id="form",
        ),
        rx.el.span(TextAreaState.seen.to_string(), id="seen"),
        rx.el.span(TextAreaState.bound, id="bound-value"),
        rx.el.span(TextAreaState.submitted.to_string(), id="submitted"),
        rx.el.span(TextAreaState.submissions.to_string(), id="submissions"),
    ),
)


@CONTRACT.step("is a textarea with its attributes in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    notes = run.server.element("notes")
    assert (notes.tag, notes.attributes["placeholder"], notes.attributes["rows"]) == (
        "textarea",
        "Your notes",
        "2",
    )
    assert run.server.element("off").text == "off"
    assert "disabled" in run.server.element("off").attributes
    assert "readonly" in run.server.element("fixed").attributes
    assert run.server.element("bound").text == "start"


@CONTRACT.step("takes the focus and text with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    page = run.page
    page.get_by_text("Notes", exact=True).click()
    assert focused(page) == "notes"
    page.keyboard.type("one")
    page.keyboard.press("Enter")
    page.keyboard.type("two")
    assert page.locator("#notes").input_value() == "one\ntwo"


@CONTRACT.step("has the role and the name of a text box, and its label")
def _role(run: Run) -> None:
    page = run.page
    assert page.get_by_role("textbox", name="Notes").get_attribute("id") == "notes"
    assert page.get_by_label("Notes", exact=True).get_attribute("id") == "notes"
    assert page.get_by_role("textbox", name="Events").get_attribute("id") == "events"
    assert page.get_by_role("textbox", disabled=True).count() == 1


@CONTRACT.step("Tab stops on each text area but a disabled one")
def _tab(run: Run) -> None:
    stops = []
    for _ in range(4):
        run.page.keyboard.press("Tab")
        stops.append(focused(run.page))
    assert stops == ["notes", "fixed", "events", "bound"]


@CONTRACT.step("typing changes the text and says so, key by key")
def _type(run: Run) -> None:
    page = run.page
    page.locator("#notes").focus()
    page.keyboard.type("Ada", delay=30)
    assert page.locator("#notes").input_value() == "Ada"
    wait_for_text(page, "seen", '["A","Ad","Ada"]')


@CONTRACT.step("focus and blur hand over the text")
def _focus_blur(run: Run) -> None:
    page = run.page
    page.locator("#events").focus()
    wait_for_text(page, "seen", '["e"]')
    page.keyboard.press("Control+End")
    page.keyboard.type("x")
    page.keyboard.press("Tab")
    wait_for_text(page, "seen", '["e","ex"]')


@CONTRACT.step(
    "a disabled text area takes no text, and a read-only one the focus alone"
)
def _disabled(run: Run) -> None:
    page = run.page
    assert page.locator("#off").is_disabled()
    page.locator("#fixed").focus()
    page.keyboard.type("x")
    assert page.locator("#fixed").input_value() == "fixed"
    assert focused(page) == "fixed"


@CONTRACT.step("a text area bound to state keeps what is typed and follows the state")
def _bound(run: Run) -> None:
    page = run.page
    bound = page.locator("#bound")
    assert bound.input_value() == "start"
    bound.focus()
    page.keyboard.press("Control+End")
    page.keyboard.type(" and more", delay=15)
    assert bound.input_value() == "start and more"
    wait_for_text(page, "bound-value", "start and more")
    assert bound.input_value() == "start and more"
    page.locator("#reset").click()
    wait_for_text(page, "bound-value", "reset")
    page.wait_for_function("document.getElementById('bound').value === 'reset'")


@CONTRACT.step("rx.set_value and rx.set_focus reach the textarea by its id")
def _refs(run: Run) -> None:
    page = run.page
    page.locator("#set").click()
    page.wait_for_function("document.getElementById('notes').value === 'set'")
    page.locator("#focus").click()
    page.wait_for_function("document.activeElement.id === 'notes'")


@CONTRACT.step("submits its text with a form")
def _submit(run: Run) -> None:
    page = run.page
    page.locator("#q").focus()
    page.keyboard.type("abcdefg")
    assert page.locator("#q").input_value() == "abcd"
    page.locator("#send").click()
    wait_for_text(page, "submissions", "1")
    assert page.locator("#submitted").text_content() == '{"q":"abcd"}'


@CONTRACT.step("a required text area holds its form back until it has text")
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
