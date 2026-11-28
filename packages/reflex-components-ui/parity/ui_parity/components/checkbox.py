"""The checkbox: every variant, size and state, and what a native input gives it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import ACTIVE, DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import ACCENTS

VARIANTS = ["classic", "surface", "soft"]
SIZES = ["1", "2", "3"]
STATES = ["rest", HOVER, FOCUS_VISIBLE, ACTIVE]
# The checkbox itself, inside its label: a button of Radix, an input here.
TARGET = ("button", "input")


def _checkbox(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a checkbox with its label.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``text`` is the label.

    Returns:
        The checkbox.
    """
    props = dict(props)
    return namespace.checkbox(props.pop("text", "Agree"), **props)


MATRIX = Matrix(
    component="checkbox",
    render=_checkbox,
    base={"default_checked": True},
    cross={"variant": VARIANTS, "size": SIZES, "default_checked": [True, False]},
    sweep={
        "color_scheme": ACCENTS,
        "high_contrast": [True],
        "disabled": [True],
        "text": {"none": ""},
        "spacing": ["1", "4"],
        "appearance": [DARK],
        "state": STATES,
    },
    groups=[
        {
            "variant": VARIANTS,
            "default_checked": [True, False],
            "high_contrast": [False, True],
            "appearance": [LIGHT, DARK],
        },
        {
            "variant": VARIANTS,
            "default_checked": [True, False],
            "disabled": [True],
            "appearance": [LIGHT, DARK],
        },
        {
            "variant": VARIANTS,
            "default_checked": [True, False],
            "state": STATES,
        },
        {
            "variant": VARIANTS,
            "color_scheme": ["ruby", "gray", "yellow"],
            "high_contrast": [False, True],
        },
    ],
    stage=(160, 64),
    crop="stage",
    target=TARGET,
    # Not held to zero, for the check alone: Radix Themes draws it as an svg
    # element and an input has no children, so here it is the same path as a
    # mask, whose edge the browser rasterizes by a step of a channel
    # otherwise. At a threshold of zero 96 of the 132 cells are equal, every
    # unchecked one among them, and the others differ by at most 28 pixels of
    # 10240 on that edge. At the default threshold one cell differs, by 3
    # pixels: the check of the smallest size lies on half a pixel.
    tolerance=0.0005,
)


class CheckboxState(rx.State):
    """What the checkboxes of the contract are bound to."""

    bound: rx.Field[bool] = rx.field(False)
    seen: rx.Field[list[bool]] = rx.field(default_factory=list)
    submitted: rx.Field[dict[str, str]] = rx.field(default_factory=dict)
    submissions: rx.Field[int] = rx.field(0)

    @rx.event
    def set_bound(self, checked: bool):
        """Follow the bound checkbox.

        Args:
            checked: Whether it is checked.
        """
        self.bound = checked

    @rx.event
    def see(self, checked: bool):
        """Keep what a change handed over.

        Args:
            checked: Whether the checkbox is checked.
        """
        self.seen.append(checked)

    @rx.event
    def flip(self):
        """Change the bound value from outside the checkbox."""
        self.bound = not self.bound

    @rx.event
    def submit(self, data: dict[str, str]):
        """Keep what a form submitted.

        Args:
            data: The values of the form.
        """
        self.submitted = data
        self.submissions += 1


CONTRACT = Contract(
    component="checkbox",
    render=lambda namespace: namespace.box(
        namespace.checkbox("Agree", id="agree", on_change=CheckboxState.see),
        namespace.checkbox("Off", id="off", disabled=True),
        namespace.checkbox(
            "Bound",
            id="bound",
            checked=CheckboxState.bound,
            on_change=CheckboxState.set_bound,
        ),
        rx.el.button("Flip", id="flip", on_click=CheckboxState.flip),
        rx.el.form(
            namespace.checkbox("News", id="news", name="news"),
            namespace.checkbox("Plan", id="plan", name="plan", value="pro"),
            namespace.checkbox("Was", id="was", name="was", default_checked=True),
            namespace.checkbox("Terms", id="terms", name="terms", required=True),
            rx.el.button("Send", id="send", type="submit"),
            on_submit=CheckboxState.submit,
            id="form",
        ),
        rx.el.span(CheckboxState.seen.to_string(), id="seen"),
        rx.el.span(CheckboxState.bound.to_string(), id="bound-value"),
        rx.el.span(CheckboxState.submitted.to_string(), id="submitted"),
        rx.el.span(CheckboxState.submissions.to_string(), id="submissions"),
    ),
)


def _focused(run: Run) -> str:
    """Read which element has the focus.

    Args:
        run: The run, on a page.

    Returns:
        The id of the element.
    """
    return run.page.evaluate("document.activeElement.id")


@CONTRACT.step("its label is in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    assert "id" in run.server.element("agree").attributes
    assert "disabled" in run.server.element("off").attributes
    assert run.server.element("form").text == "NewsPlanWasTermsSend"


@CONTRACT.step("is checked by a click with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    page = run.page
    page.keyboard.press("Tab")
    assert _focused(run) == "agree"
    page.get_by_text("Agree").click()
    assert page.locator("#agree").is_checked()
    assert page.locator("#was").is_checked()
    assert page.locator("#off").is_disabled()


@CONTRACT.step("has the role, the name and the state of a checkbox")
def _role(run: Run) -> None:
    page = run.page
    agree = page.get_by_role("checkbox", name="Agree")
    assert agree.get_attribute("id") == "agree"
    assert not agree.is_checked()
    assert page.get_by_role("checkbox", name="Was", checked=True).count() == 1
    assert page.get_by_role("checkbox", name="Off", disabled=True).count() == 1
    assert page.get_by_role("checkbox").count() == 7


@CONTRACT.step("Tab skips a disabled checkbox")
def _tab(run: Run) -> None:
    focused = []
    for _ in range(3):
        run.page.keyboard.press("Tab")
        focused.append(_focused(run))
    assert focused == ["agree", "bound", "flip"]
    run.page.keyboard.press("Shift+Tab")
    assert _focused(run) == "bound"
    assert run.page.locator("#bound").evaluate(
        "element => element.matches(':focus-visible')"
    )


@CONTRACT.step("Space and a click on its label toggle it, and say so")
def _toggle(run: Run) -> None:
    page = run.page
    agree = page.locator("#agree")
    agree.focus()
    page.keyboard.press("Space")
    assert agree.is_checked()
    page.keyboard.press("Space")
    assert not agree.is_checked()
    page.get_by_text("Agree").click()
    assert agree.is_checked()
    agree.click()
    assert not agree.is_checked()
    page.wait_for_function(
        "document.getElementById('seen').textContent === '[true,false,true,false]'"
    )


@CONTRACT.step("Enter does not toggle it")
def _enter(run: Run) -> None:
    agree = run.page.locator("#agree")
    agree.focus()
    run.page.keyboard.press("Enter")
    assert not agree.is_checked()


@CONTRACT.step("Enter on a checkbox does not submit its form")
def _enter_in_form(run: Run) -> None:
    page = run.page
    page.locator("#terms").check()
    page.locator("#news").focus()
    page.keyboard.press("Enter")
    page.locator("#flip").click()
    page.wait_for_function(
        "document.getElementById('bound-value').textContent === 'true'"
    )
    assert page.locator("#submissions").text_content() == "0"


@CONTRACT.step("a disabled checkbox is not toggled")
def _disabled(run: Run) -> None:
    off = run.page.locator("#off")
    off.click(force=True)
    run.page.get_by_text("Off").click(force=True)
    assert not off.is_checked()


@CONTRACT.step("follows the state it is bound to")
def _bound(run: Run) -> None:
    page = run.page
    bound = page.locator("#bound")
    bound.click()
    page.wait_for_function(
        "document.getElementById('bound-value').textContent === 'true'"
    )
    assert bound.is_checked()
    page.locator("#flip").click()
    page.wait_for_function(
        "document.getElementById('bound-value').textContent === 'false'"
    )
    page.wait_for_function(
        "!document.getElementById('bound').matches(':checked, [aria-checked=true]')"
    )
    assert not bound.is_checked()


@CONTRACT.step("submits its value with a form when it is checked")
def _submit(run: Run) -> None:
    page = run.page
    page.locator("#plan").check()
    page.locator("#terms").check()
    page.locator("#send").click()
    page.wait_for_function("document.getElementById('submissions').textContent === '1'")
    assert page.locator("#submitted").text_content() == (
        '{"plan":true,"was":true,"terms":true,"news":false}'
    )


@CONTRACT.step("a required checkbox holds its form back until it is checked")
def _required(run: Run) -> None:
    page = run.page
    page.locator("#send").click()
    # An event that does reach the server comes back after the blocked one.
    page.locator("#flip").click()
    page.wait_for_function(
        "document.getElementById('bound-value').textContent === 'true'"
    )
    assert page.locator("#submissions").text_content() == "0"
    page.locator("#terms").check()
    page.locator("#send").click()
    page.wait_for_function("document.getElementById('submissions').textContent === '1'")
