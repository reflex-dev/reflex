"""The tooltip: on each side of what it describes, and when it opens and closes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from playwright.sync_api import Locator, Page

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.look import Point, State
from ui_parity.matrix import DARK, FOCUS_VISIBLE, LIGHT, Matrix
from ui_parity.samples import wait_for_text

SIDES = ["top", "right", "bottom", "left"]
ALIGNS = ["start", "center", "end"]
OPEN = "open"
# A tooltip that is shown, in either system.
SHOWN = ".rt-TooltipContent, [role=tooltip]:popover-open"
LONG = (
    "A tooltip with more to say than one line holds, which wraps where a "
    "tooltip is as wide as it may be."
)


def _tooltip(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a button with a tooltip.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the tooltip. ``long`` asks for a text of
            several lines, and ``themed`` for a theme of another radius
            around it.

    Returns:
        The button, with room around it for its tooltip on any side.
    """
    props = dict(props)
    long, themed = props.pop("long", False), props.pop("themed", False)
    shown = namespace.tooltip(
        namespace.button("Save", width="80px"),
        content=LONG if long else "Saves the file",
        # The cells do not wait for the pointer to rest.
        delay_duration=0,
        # On the pixel grid wherever it is beside its button: Radix rounds
        # where it puts a tooltip, and the browser does not.
        width="260px" if long else "120px",
        **props,
    )
    if themed:
        shown = namespace.theme(shown, radius="full")
    return rx.el.div(shown, style={"padding": "70px 0 0 150px"})


def _show(page: Page, target: Locator, point: Point) -> None:
    """Put the pointer on what a tooltip describes, and wait for the tooltip.

    Args:
        page: The page.
        target: The button.
        point: The middle of the button.
    """
    page.mouse.move(*point)
    page.locator(SHOWN).first.wait_for()


def leave(page: Page) -> None:
    """Take the pointer off a button and its tooltip.

    Args:
        page: The page.
    """
    # Twice: Radix looks where the pointer went when it moves again.
    page.mouse.move(0, 0)
    page.mouse.move(2, 2)


def _hide(page: Page, target: Locator, point: Point) -> None:
    """Take the pointer off, and wait until the tooltip is gone.

    Args:
        page: The page.
        target: The button.
        point: The middle of the button.
    """
    leave(page)
    page.locator(SHOWN).first.wait_for(state="detached")


MATRIX = Matrix(
    component="tooltip",
    render=_tooltip,
    sweep={
        "side": SIDES,
        "long": [True],
        "appearance": [DARK],
        "state": [FOCUS_VISIBLE, OPEN],
    },
    groups=[
        {"side": SIDES, "align": ALIGNS, "state": [OPEN]},
        {"side": SIDES, "side_offset": [0, 12], "state": [OPEN]},
        {"long": [True], "side": ["top", "bottom"], "state": [OPEN]},
        {"themed": [True], "state": [OPEN]},
        {"state": [FOCUS_VISIBLE, OPEN], "appearance": [LIGHT, DARK]},
    ],
    stage=(480, 200),
    crop="stage",
    target="button",
    states={
        OPEN: State(
            enter=_show,
            leave=_hide,
            matches=":is([data-state='delayed-open'], [data-state='instant-open'])",
        )
    },
    # Held to a threshold of zero, and to the arrow: the tooltip of Radix has
    # one between it and its button, of 16 to 27 pixels of 96000, and the
    # one here has none. Nothing else differs in any cell.
    threshold=0,
    tolerance=0.0003,
)


class TooltipState(rx.State):
    """What the tooltips of the contract are bound to."""

    shown: rx.Field[bool] = rx.field(False)
    seen: rx.Field[list[str]] = rx.field(default_factory=list)

    @rx.event
    def set_shown(self, value: bool):
        """Follow the bound tooltip.

        Args:
            value: Whether it is open.
        """
        self.shown = value

    @rx.event
    def see_open(self, value: bool):
        """Keep whether a tooltip opened or closed.

        Args:
            value: Whether it is open.
        """
        self.seen.append("open" if value else "closed")

    @rx.event
    def see(self, what: str):
        """Keep what happened to a tooltip.

        Args:
            what: The event.
        """
        self.seen.append(what)


def _contract(namespace: Any) -> Any:
    """Create what the contract page shows.

    Args:
        namespace: ``rx`` or ``rx.ui``.

    Returns:
        Buttons with a tooltip: one that says what happens to it, one that
        opens at once, one whose tooltip the pointer cannot rest on, one
        bound to state, one in a dialog and one in a dark theme.
    """
    tooltip, dialog, button = namespace.tooltip, namespace.dialog, namespace.button
    return namespace.flex(
        tooltip(
            button("Save", id="save"),
            content="Saves the file",
            on_open_change=TooltipState.see_open,
            on_escape_key_down=TooltipState.see("escape"),
            on_pointer_down_outside=TooltipState.see("outside"),
        ),
        tooltip(button("Copy", id="copy"), content="Copies the text", delay_duration=0),
        tooltip(
            button("Cut", id="cut"),
            content="Cuts the text",
            delay_duration=0,
            disable_hoverable_content=True,
        ),
        tooltip(
            button("Bound", id="bound"),
            content="Follows its state",
            open=TooltipState.shown,
            on_open_change=TooltipState.set_shown,
        ),
        rx.el.button("Show", id="show", on_click=TooltipState.set_shown(True)),
        dialog.root(
            dialog.trigger(button("Dialog", id="dialog-open")),
            dialog.content(
                dialog.title("With a tooltip"),
                tooltip(
                    button("Inside", id="inside"),
                    content="In a dialog",
                    delay_duration=0,
                ),
                id="dialog-panel",
            ),
        ),
        namespace.theme(
            tooltip(button("Dark", id="dark"), content="In the dark", delay_duration=0),
            appearance="dark",
        ),
        rx.el.span(TooltipState.seen.to_string(), id="seen"),
        rx.el.span(TooltipState.shown.to_string(), id="shown"),
        spacing="4",
        padding="60px 0 0 0",
        wrap="wrap",
    )


CONTRACT = Contract(component="tooltip", render=_contract)

# The text of each tooltip that is shown.
SHOWING = (
    "[...document.querySelectorAll('.rt-TooltipContent, [role=tooltip]:popover-open')]"
    ".map(tooltip => tooltip.querySelector('p').textContent)"
)
# What describes an element to assistive technology, by its id.
DESCRIBED = (
    "id => (document.getElementById(document.getElementById(id)"
    ".getAttribute('aria-describedby') ?? '')?.textContent ?? null)"
)


def _wait_for_shown(run: Run, *texts: str) -> None:
    """Wait until the tooltips that are shown are the ones expected.

    Args:
        run: The run, on a page.
        *texts: The text of each tooltip that is to be shown.
    """
    run.page.wait_for_function(
        f"texts => JSON.stringify({SHOWING}) === JSON.stringify(texts)",
        arg=list(texts),
    )


def _shown(run: Run) -> list[str]:
    """Read which tooltips are shown.

    Args:
        run: The run, on a page.

    Returns:
        The text of each.
    """
    return run.page.evaluate(SHOWING)


@CONTRACT.step("what it describes is in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    button = run.server.element("save")
    assert (button.tag, button.text) == ("button", "Save")


@CONTRACT.step("describes its button with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    assert run.page.evaluate(DESCRIBED, "save") == "Saves the file"
    assert _shown(run) == []


@CONTRACT.step(
    "opens once the pointer has rested on its button, and closes when it leaves"
)
def _hover(run: Run) -> None:
    page = run.page
    page.locator("#save").hover()
    page.wait_for_timeout(100)
    assert _shown(run) == []
    _wait_for_shown(run, "Saves the file")
    leave(page)
    _wait_for_shown(run)
    wait_for_text(page, "seen", '["open","closed"]')


@CONTRACT.step("opens with the focus of the keyboard, and closes when it leaves")
def _focus(run: Run) -> None:
    page = run.page
    page.keyboard.press("Tab")
    _wait_for_shown(run, "Saves the file")
    page.keyboard.press("Tab")
    _wait_for_shown(run, "Copies the text")
    page.keyboard.press("Shift+Tab")
    _wait_for_shown(run, "Saves the file")


@CONTRACT.step("is the description of its button while it is shown")
def _described(run: Run) -> None:
    page = run.page
    page.keyboard.press("Tab")
    _wait_for_shown(run, "Saves the file")
    assert page.evaluate(DESCRIBED, "save") == "Saves the file"
    assert page.get_by_role("tooltip").count() == 1


@CONTRACT.step("Escape closes it, with the focus and under the pointer, and says so")
def _escape(run: Run) -> None:
    page = run.page
    page.keyboard.press("Tab")
    _wait_for_shown(run, "Saves the file")
    page.keyboard.press("Escape")
    _wait_for_shown(run)
    wait_for_text(page, "seen", '["open","escape","closed"]')
    page.locator("#copy").hover()
    _wait_for_shown(run, "Copies the text")
    page.keyboard.press("Escape")
    _wait_for_shown(run)


@CONTRACT.step("a press on its button closes it")
def _press(run: Run) -> None:
    page = run.page
    page.locator("#copy").hover()
    _wait_for_shown(run, "Copies the text")
    page.mouse.down()
    _wait_for_shown(run)
    page.mouse.up()
    page.wait_for_timeout(300)
    assert _shown(run) == []


@CONTRACT.step("the pointer can go from the button to its tooltip")
def _hoverable(run: Run) -> None:
    page = run.page
    page.locator("#copy").hover()
    _wait_for_shown(run, "Copies the text")
    box = page.locator(SHOWN).first.bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=4)
    page.wait_for_timeout(400)
    assert _shown(run) == ["Copies the text"]
    leave(page)
    _wait_for_shown(run)


@CONTRACT.step("a tooltip the pointer cannot rest on closes when it leaves the button")
def _not_hoverable(run: Run) -> None:
    page = run.page
    page.locator("#cut").hover()
    _wait_for_shown(run, "Cuts the text")
    box = page.locator(SHOWN).first.bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=4)
    _wait_for_shown(run)


@CONTRACT.step("a tooltip bound to state follows it")
def _bound(run: Run) -> None:
    page = run.page
    page.locator("#show").click()
    _wait_for_shown(run, "Follows its state")
    wait_for_text(page, "shown", "true")
    page.keyboard.press("Escape")
    _wait_for_shown(run)
    wait_for_text(page, "shown", "false")
    page.locator("#bound").hover()
    _wait_for_shown(run, "Follows its state")
    wait_for_text(page, "shown", "true")


@CONTRACT.step("a tooltip in a dialog shows over it")
def _in_dialog(run: Run) -> None:
    page = run.page
    page.locator("#dialog-open").click()
    page.locator("#dialog-panel").wait_for()
    page.locator("#inside").hover()
    _wait_for_shown(run, "In a dialog")
    box = page.locator(SHOWN).first.bounding_box()
    assert box is not None
    assert page.evaluate(
        "([x, y]) => document.elementFromPoint(x, y).closest("
        "'.rt-TooltipContent, [role=tooltip]') !== null",
        [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2],
    )
    page.keyboard.press("Escape")
    _wait_for_shown(run)
    page.locator("#dialog-panel").wait_for()


@CONTRACT.step("points at its button with an arrow")
def _arrow(run: Run) -> None:
    page = run.page
    page.locator("#copy").hover()
    _wait_for_shown(run, "Copies the text")
    assert page.locator(SHOWN).first.locator("svg").count() == 1


@CONTRACT.step("the dark appearance of a theme around a tooltip reaches it")
def _themed_dark(run: Run) -> None:
    page = run.page
    page.locator("#dark").hover()
    _wait_for_shown(run, "In the dark")
    page.wait_for_timeout(300)
    assert page.locator(SHOWN).first.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    ) == ("rgb(238, 238, 238)")
