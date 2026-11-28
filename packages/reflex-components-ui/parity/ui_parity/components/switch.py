"""The switch: every variant, size and state, and what a native input gives it."""

from __future__ import annotations

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import ACTIVE, DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import ACCENTS

VARIANTS = ["classic", "surface", "soft"]
SIZES = ["1", "2", "3"]
STATES = ["rest", HOVER, FOCUS_VISIBLE, ACTIVE]
ON_OFF = [True, False]

MATRIX = Matrix(
    component="switch",
    base={"default_checked": True},
    cross={"variant": VARIANTS, "size": SIZES, "default_checked": ON_OFF},
    sweep={
        "color_scheme": ACCENTS,
        "radius": ["none", "small", "full"],
        "high_contrast": [True],
        "disabled": [True],
        "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
        "appearance": [DARK],
        "state": STATES,
        "viewport": [520],
    },
    groups=[
        {
            "variant": VARIANTS,
            "default_checked": ON_OFF,
            "high_contrast": [False, True],
            "appearance": [LIGHT, DARK],
        },
        {
            "variant": VARIANTS,
            "default_checked": ON_OFF,
            "disabled": [True],
            "appearance": [LIGHT, DARK],
        },
        {
            "variant": VARIANTS,
            "default_checked": ON_OFF,
            "high_contrast": [False, True],
            "state": STATES,
        },
        {
            "variant": VARIANTS,
            "default_checked": [True],
            "state": [ACTIVE],
            "high_contrast": [False, True],
            "appearance": [DARK],
        },
        {
            "variant": VARIANTS,
            "color_scheme": ["ruby", "gray", "yellow"],
            "high_contrast": [False, True],
        },
        {"radius": ["none", "small", "full"], "size": SIZES},
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
            "viewport": [520, 800, 1100],
        },
    ],
    stage=(120, 64),
    # The thumb is drawn by the switch itself here, where Radix has an
    # element for it.
    parts={
        "track": ("button::before", "input::before"),
        "thumb": ("button > span", "input::after"),
    },
    # Not held to zero. At a threshold of zero 132 of the 164 cells are equal
    # pixel for pixel, the base cell among them, and the others differ by
    # where they are on the page: the gradient of the track is dithered and
    # the blurred shadows of the thumb are rasterized by a step of a channel
    # otherwise, on at most 8 pixels of 1408. At the default threshold 5 cells
    # differ, by at most 3 pixels of 1836.
    tolerance=0.002,
)


class SwitchState(rx.State):
    """What the switches of the contract are bound to."""

    bound: rx.Field[bool] = rx.field(False)
    seen: rx.Field[list[bool]] = rx.field(default_factory=list)
    submitted: rx.Field[dict[str, str]] = rx.field(default_factory=dict)
    submissions: rx.Field[int] = rx.field(0)

    @rx.event
    def set_bound(self, checked: bool):
        """Follow the bound switch.

        Args:
            checked: Whether it is on.
        """
        self.bound = checked

    @rx.event
    def see(self, checked: bool):
        """Keep what a change handed over.

        Args:
            checked: Whether the switch is on.
        """
        self.seen.append(checked)

    @rx.event
    def flip(self):
        """Change the bound value from outside the switch."""
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
    component="switch",
    render=lambda namespace: namespace.box(
        rx.el.label("Wifi", namespace.switch(id="wifi", on_change=SwitchState.see)),
        namespace.switch(id="off", disabled=True, aria_label="Off"),
        namespace.switch(
            id="bound",
            aria_label="Bound",
            checked=SwitchState.bound,
            on_change=SwitchState.set_bound,
        ),
        rx.el.button("Flip", id="flip", on_click=SwitchState.flip),
        rx.el.form(
            namespace.switch(id="news", name="news", aria_label="News"),
            namespace.switch(id="plan", name="plan", value="pro", aria_label="Plan"),
            namespace.switch(
                id="was", name="was", default_checked=True, aria_label="Was"
            ),
            namespace.switch(
                id="terms", name="terms", required=True, aria_label="Terms"
            ),
            rx.el.button("Send", id="send", type="submit"),
            on_submit=SwitchState.submit,
            id="form",
        ),
        rx.el.span(SwitchState.seen.to_string(), id="seen"),
        rx.el.span(SwitchState.bound.to_string(), id="bound-value"),
        rx.el.span(SwitchState.submitted.to_string(), id="submitted"),
        rx.el.span(SwitchState.submissions.to_string(), id="submissions"),
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


def _wait_for_text(run: Run, element: str, text: str) -> None:
    """Wait until an element holds a text.

    Args:
        run: The run, on a page.
        element: The id of the element.
        text: The whole text.
    """
    run.page.wait_for_function(
        "([id, text]) => document.getElementById(id).textContent === text",
        arg=[element, text],
    )


@CONTRACT.step("is a switch in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    wifi = run.server.element("wifi").attributes
    assert wifi["role"] == "switch"
    assert "disabled" in run.server.element("off").attributes


@CONTRACT.step("is turned on by a click with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    page = run.page
    page.keyboard.press("Tab")
    assert _focused(run) == "wifi"
    page.get_by_text("Wifi").click()
    assert page.locator("#wifi").is_checked()
    assert page.locator("#was").is_checked()
    assert page.locator("#off").is_disabled()


@CONTRACT.step("has the role, the name and the state of a switch")
def _role(run: Run) -> None:
    page = run.page
    wifi = page.get_by_role("switch", name="Wifi")
    assert wifi.get_attribute("id") == "wifi"
    assert not wifi.is_checked()
    assert page.get_by_role("switch", name="Was", checked=True).count() == 1
    assert page.get_by_role("switch", name="Off", disabled=True).count() == 1
    assert page.get_by_role("switch").count() == 7


@CONTRACT.step("Tab skips a disabled switch")
def _tab(run: Run) -> None:
    focused = []
    for _ in range(3):
        run.page.keyboard.press("Tab")
        focused.append(_focused(run))
    assert focused == ["wifi", "bound", "flip"]
    run.page.keyboard.press("Shift+Tab")
    assert _focused(run) == "bound"
    assert run.page.locator("#bound").evaluate(
        "element => element.matches(':focus-visible')"
    )


@CONTRACT.step("Space and a click on it or on its label toggle it, and say so")
def _toggle(run: Run) -> None:
    page = run.page
    wifi = page.locator("#wifi")
    wifi.focus()
    page.keyboard.press("Space")
    assert wifi.is_checked()
    page.keyboard.press("Space")
    assert not wifi.is_checked()
    page.get_by_text("Wifi").click(position={"x": 4, "y": 4})
    assert wifi.is_checked()
    wifi.click()
    assert not wifi.is_checked()
    _wait_for_text(run, "seen", "[true,false,true,false]")


@CONTRACT.step("Enter toggles it")
def _enter(run: Run) -> None:
    wifi = run.page.locator("#wifi")
    wifi.focus()
    run.page.keyboard.press("Enter")
    assert wifi.is_checked()


@CONTRACT.step("Enter on a switch does not submit its form")
def _enter_in_form(run: Run) -> None:
    page = run.page
    page.locator("#terms").check()
    page.locator("#news").focus()
    page.keyboard.press("Enter")
    page.locator("#flip").click()
    _wait_for_text(run, "bound-value", "true")
    assert page.locator("#submissions").text_content() == "0"


@CONTRACT.step("a disabled switch is not toggled")
def _disabled(run: Run) -> None:
    off = run.page.locator("#off")
    off.click(force=True)
    assert not off.is_checked()


@CONTRACT.step("follows the state it is bound to")
def _bound(run: Run) -> None:
    page = run.page
    bound = page.locator("#bound")
    bound.click()
    _wait_for_text(run, "bound-value", "true")
    assert bound.is_checked()
    page.locator("#flip").click()
    _wait_for_text(run, "bound-value", "false")
    page.wait_for_function(
        "!document.getElementById('bound').matches(':checked, [aria-checked=true]')"
    )
    assert not bound.is_checked()


@CONTRACT.step("submits with a form whether it is on")
def _submit(run: Run) -> None:
    page = run.page
    page.locator("#plan").check()
    page.locator("#terms").check()
    page.locator("#send").click()
    _wait_for_text(run, "submissions", "1")
    assert page.locator("#submitted").text_content() == (
        '{"plan":true,"was":true,"terms":true,"news":false}'
    )


@CONTRACT.step("a required switch holds its form back until it is on")
def _required(run: Run) -> None:
    page = run.page
    page.locator("#send").click()
    # An event that does reach the server comes back after the blocked one.
    page.locator("#flip").click()
    _wait_for_text(run, "bound-value", "true")
    assert page.locator("#submissions").text_content() == "0"
    page.locator("#terms").check()
    page.locator("#send").click()
    _wait_for_text(run, "submissions", "1")
