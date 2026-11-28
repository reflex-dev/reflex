"""The popover: closed and open in every size, on each side of its trigger, and how it closes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from playwright.sync_api import Locator, Page

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.look import Point, State
from ui_parity.matrix import DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import PARAGRAPH, wait_for_text

SIZES = ["1", "2", "3", "4"]
SIDES = ["top", "right", "bottom", "left"]
ALIGNS = ["start", "center", "end"]
OPEN = "open"
# A popup that is open, in either system.
SHOWN = "[data-radix-popper-content-wrapper], :popover-open"


def _popover(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a popover and the button that opens it.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the content. ``variant`` is the one of the
            button that opens it, ``long`` asks for more than the page has
            room for, and ``themed`` for a theme of another accent and
            radius around the popover.

    Returns:
        The popover, with room around its trigger for it to open on any
        side.
    """
    props = dict(props)
    popover = namespace.popover
    long, themed = props.pop("long", False), props.pop("themed", False)
    if long:
        # Within the page in whichever column its frame is.
        props["width"] = "260px"
    if "align" in props or "side" in props:
        # On the pixel grid wherever it is along its trigger: Radix rounds
        # where it puts a popover, and the browser does not.
        props["width"] = "200px"
    shown = popover.root(
        popover.trigger(
            namespace.button("Open", variant=props.pop("variant", "soft"), width="80px")
        ),
        popover.content(
            namespace.text("Dimensions", size="2", weight="bold"),
            *(
                rx.el.p(f"{number}. {PARAGRAPH}")
                for number in range(1, 30 if long else 1)
            ),
            popover.close(namespace.button("Done", size="1")),
            **props,
        ),
    )
    if themed:
        shown = namespace.theme(shown, accent_color="ruby", radius="full")
    return rx.el.div(shown, style={"padding": "120px 0 0 230px"})


def open_popup(page: Page, target: Locator, point: Point) -> None:
    """Open a popup from its trigger, and wait for it.

    Args:
        page: The page.
        target: The trigger.
        point: The middle of the trigger.
    """
    target.click()
    page.locator(SHOWN).first.wait_for()
    # The pointer is not left on the trigger.
    page.mouse.move(1, 1)


def close_popup(page: Page, target: Locator, point: Point) -> None:
    """Close the open popup, and take the focus off whatever has it.

    Args:
        page: The page.
        target: The trigger.
        point: The middle of the trigger.
    """
    page.keyboard.press("Escape")
    page.locator(SHOWN).first.wait_for(state="detached")
    page.evaluate("document.activeElement.blur()")


OPENED = State(enter=open_popup, leave=close_popup, matches="[data-state='open']")

MATRIX = Matrix(
    component="popover",
    render=_popover,
    sweep={
        "size": SIZES,
        "variant": ["solid", "classic", "surface", "ghost", "outline"],
        "appearance": [DARK],
        "state": [HOVER, FOCUS_VISIBLE, OPEN],
    },
    groups=[
        {"size": SIZES, "state": [OPEN], "appearance": [LIGHT, DARK]},
        {"side": SIDES, "align": ALIGNS, "state": [OPEN]},
        {"side": SIDES, "side_offset": [0, 20], "state": [OPEN]},
        {"align": ["start", "end"], "align_offset": [12], "state": [OPEN]},
        {"themed": [True], "state": [OPEN], "appearance": [LIGHT, DARK]},
        {"long": [True], "state": [OPEN]},
        {
            "variant": ["solid", "classic", "surface", "ghost", "outline"],
            "state": [OPEN],
        },
    ],
    stage=(560, 340),
    crop="stage",
    target="button",
    states={OPEN: OPENED},
    # Not held to zero. At a threshold of zero 40 of the 45 cells are equal
    # pixel for pixel, and the others differ by one pixel of 190400 on the
    # edge of the trigger, whose gradient or ring the browser dithers by
    # where the button is on the page: at the default threshold 3 cells do.
    tolerance=0.00001,
)


class PopoverState(rx.State):
    """What the popovers of the contract are bound to."""

    shown: rx.Field[bool] = rx.field(False)
    seen: rx.Field[list[str]] = rx.field(default_factory=list)
    clicks: rx.Field[int] = rx.field(0)

    @rx.event
    def set_shown(self, value: bool):
        """Follow the bound popover.

        Args:
            value: Whether it is open.
        """
        self.shown = value

    @rx.event
    def see_open(self, value: bool):
        """Keep whether a popover opened or closed.

        Args:
            value: Whether it is open.
        """
        self.seen.append("open" if value else "closed")

    @rx.event
    def see(self, what: str):
        """Keep what happened to a popover.

        Args:
            what: The event.
        """
        self.seen.append(what)

    @rx.event
    def save(self):
        """Close the bound popover from the backend."""
        self.shown = False

    @rx.event
    def click(self):
        """Count a click on the button beside the popovers."""
        self.clicks += 1


def _contract(namespace: Any) -> Any:
    """Create what the contract page shows.

    Args:
        namespace: ``rx`` or ``rx.ui``.

    Returns:
        A popover that says what happens to it, one bound to state, one in
        a dialog and one in a theme of its own.
    """
    popover, dialog, button = namespace.popover, namespace.dialog, namespace.button
    return namespace.box(
        popover.root(
            popover.trigger(button("Open", id="open")),
            popover.content(
                rx.el.input(id="field"),
                popover.close(button("Close", id="close")),
                id="panel",
                on_open_auto_focus=PopoverState.see("focus-in"),
                on_close_auto_focus=PopoverState.see("focus-out"),
                on_escape_key_down=PopoverState.see("escape"),
                on_pointer_down_outside=PopoverState.see("outside"),
                on_focus_outside=PopoverState.see("focus-outside"),
                on_interact_outside=PopoverState.see("interact"),
            ),
            on_open_change=PopoverState.see_open,
        ),
        rx.el.button("Beside", id="beside", on_click=PopoverState.click),
        popover.root(
            popover.trigger(button("Bound", id="bound-open")),
            popover.content(
                button("Save", id="save", on_click=PopoverState.save),
                id="bound-panel",
            ),
            open=PopoverState.shown,
            on_open_change=PopoverState.set_shown,
        ),
        rx.el.button("Show", id="show", on_click=PopoverState.set_shown(True)),
        dialog.root(
            dialog.trigger(button("Dialog", id="dialog-open")),
            dialog.content(
                dialog.title("With a popover"),
                popover.root(
                    popover.trigger(button("Inside", id="inside-open")),
                    popover.content(
                        popover.close(button("Shut", id="inside-close")),
                        id="inside-panel",
                    ),
                ),
                id="dialog-panel",
            ),
        ),
        namespace.theme(
            popover.root(
                popover.trigger(button("Themed", id="themed-open")),
                popover.content(
                    popover.close(button("Fine", id="themed-close")),
                    id="themed-panel",
                ),
            ),
            accent_color="ruby",
            appearance="dark",
        ),
        rx.el.span(PopoverState.seen.to_string(), id="seen"),
        rx.el.span(PopoverState.shown.to_string(), id="shown"),
        rx.el.span(PopoverState.clicks.to_string(), id="clicks"),
    )


CONTRACT = Contract(component="popover", render=_contract)


def _open(run: Run, trigger: str = "open", panel: str = "panel") -> None:
    """Open a popover from its trigger, and wait until the focus is in it.

    Args:
        run: The run, on a page.
        trigger: The id of the trigger.
        panel: The id of the popover.
    """
    run.page.locator(f"#{trigger}").click()
    run.page.locator(f"#{panel}").wait_for()
    run.page.wait_for_function(
        "id => document.getElementById(id).contains(document.activeElement)",
        arg=panel,
    )


def _wait_for_closed(run: Run, panel: str = "panel") -> None:
    """Wait until a popover is closed.

    Args:
        run: The run, on a page.
        panel: The id of the popover.
    """
    run.page.locator(f"#{panel}").wait_for(state="hidden")


def _wait_for_focus(run: Run, element: str) -> None:
    """Wait until an element has the focus.

    Args:
        run: The run, on a page.
        element: Its id.
    """
    run.page.wait_for_function("id => document.activeElement.id === id", arg=element)


@CONTRACT.step("its trigger is a button in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    trigger = run.server.element("open")
    assert (trigger.tag, trigger.text, trigger.attributes["aria-haspopup"]) == (
        "button",
        "Open",
        "dialog",
    )


@CONTRACT.step("what it holds is in the server render", on=SERVER)
def _server_content(run: Run) -> None:
    assert run.server.element("panel").text == "Close"


@CONTRACT.step("opens and closes with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    page = run.page
    page.set_default_timeout(3000)
    assert not page.locator("#panel").is_visible()
    page.locator("#open").click()
    page.wait_for_timeout(300)
    assert page.locator("#panel").is_visible()
    page.locator("#close").click()
    page.wait_for_timeout(300)
    assert not page.locator("#panel").is_visible()
    page.locator("#open").click()
    page.wait_for_timeout(300)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    assert not page.locator("#panel").is_visible()


@CONTRACT.step("is a dialog its trigger says it opens")
def _role(run: Run) -> None:
    page = run.page
    trigger = page.locator("#open")
    assert trigger.get_attribute("aria-expanded") == "false"
    assert trigger.get_attribute("data-state") == "closed"
    _open(run)
    assert trigger.get_attribute("aria-expanded") == "true"
    assert trigger.get_attribute("data-state") == "open"
    assert page.get_by_role("dialog").count() == 1
    assert page.get_by_role("dialog").get_attribute("id") == "panel"


@CONTRACT.step("its trigger names the popover it opens by the id it is given")
def _controls(run: Run) -> None:
    assert run.page.locator("#open").get_attribute("aria-controls") == "panel"


@CONTRACT.step("opens beside its trigger, at its start")
def _placed(run: Run) -> None:
    page = run.page
    _open(run)
    page.wait_for_timeout(400)
    trigger, panel = (
        page.locator(f"#{element}").bounding_box() for element in ("open", "panel")
    )
    assert trigger is not None
    assert panel is not None
    assert abs(panel["x"] - trigger["x"]) < 1
    assert abs(panel["y"] - (trigger["y"] + trigger["height"] + 8)) < 1


@CONTRACT.step("the focus moves into the popover, and back to its trigger")
def _focus(run: Run) -> None:
    page = run.page
    page.locator("#open").focus()
    page.keyboard.press("Enter")
    page.locator("#panel").wait_for()
    page.wait_for_function(
        "document.getElementById('panel').contains(document.activeElement)"
    )
    page.keyboard.press("Escape")
    _wait_for_closed(run)
    _wait_for_focus(run, "open")
    page.keyboard.press("Space")
    page.locator("#panel").wait_for()
    page.locator("#close").click()
    _wait_for_closed(run)
    _wait_for_focus(run, "open")


@CONTRACT.step("Tab stays inside an open popover")
def _tab(run: Run) -> None:
    page = run.page
    _open(run)
    page.locator("#field").focus()
    stops = []
    for _ in range(4):
        page.keyboard.press("Tab")
        stops.append(page.evaluate("document.activeElement.id"))
    assert stops == ["close", "field", "close", "field"]


@CONTRACT.step("the focus leaving it closes it, and says so")
def _focus_outside(run: Run) -> None:
    page = run.page
    _open(run)
    page.locator("#beside").focus()
    _wait_for_closed(run)
    wait_for_text(
        page,
        "seen",
        '["open","focus-in","focus-outside","interact","closed","focus-out"]',
    )


@CONTRACT.step("Escape closes it, and says so")
def _escape(run: Run) -> None:
    page = run.page
    _open(run)
    wait_for_text(page, "seen", '["open","focus-in"]')
    page.keyboard.press("Escape")
    _wait_for_closed(run)
    wait_for_text(page, "seen", '["open","focus-in","escape","closed","focus-out"]')


@CONTRACT.step("a press outside closes it, and reaches the page")
def _outside(run: Run) -> None:
    page = run.page
    _open(run)
    page.locator("#panel").click(position={"x": 4, "y": 4})
    page.wait_for_timeout(200)
    assert page.locator("#panel").is_visible()
    page.locator("#beside").click()
    _wait_for_closed(run)
    wait_for_text(page, "clicks", "1")
    wait_for_text(
        page, "seen", '["open","focus-in","outside","interact","closed","focus-out"]'
    )


@CONTRACT.step("its close button closes it, and says nothing of a dismissal")
def _close(run: Run) -> None:
    page = run.page
    _open(run)
    page.locator("#close").click()
    _wait_for_closed(run)
    wait_for_text(page, "seen", '["open","focus-in","closed","focus-out"]')


@CONTRACT.step("a popover bound to state follows it, and is closed from the backend")
def _bound(run: Run) -> None:
    page = run.page
    page.locator("#show").click()
    page.locator("#bound-panel").wait_for()
    wait_for_text(page, "shown", "true")
    page.locator("#save").click()
    _wait_for_closed(run, "bound-panel")
    wait_for_text(page, "shown", "false")
    _open(run, "bound-open", "bound-panel")
    wait_for_text(page, "shown", "true")
    page.keyboard.press("Escape")
    _wait_for_closed(run, "bound-panel")
    wait_for_text(page, "shown", "false")


@CONTRACT.step(
    "a popover in a dialog opens over it, and Escape closes the popover alone"
)
def _in_dialog(run: Run) -> None:
    page = run.page
    page.locator("#dialog-open").click()
    page.locator("#dialog-panel").wait_for()
    _open(run, "inside-open", "inside-panel")
    page.keyboard.press("Escape")
    _wait_for_closed(run, "inside-panel")
    page.locator("#dialog-panel").wait_for()
    _wait_for_focus(run, "inside-open")
    _open(run, "inside-open", "inside-panel")
    page.locator("#inside-close").click()
    _wait_for_closed(run, "inside-panel")
    page.locator("#dialog-panel").wait_for()
    page.keyboard.press("Escape")
    page.locator("#dialog-panel").wait_for(state="hidden")


@CONTRACT.step("the accent of a theme around a popover reaches what it holds")
def _themed(run: Run) -> None:
    page = run.page
    _open(run, "themed-open", "themed-panel")
    page.mouse.move(1, 1)
    page.wait_for_timeout(400)
    assert page.locator("#themed-close").evaluate(
        "element => getComputedStyle(element).backgroundColor"
    ) == ("rgb(229, 70, 102)")


@CONTRACT.step("the dark appearance of a theme around a popover reaches it")
def _themed_dark(run: Run) -> None:
    page = run.page
    _open(run, "themed-open", "themed-panel")
    page.wait_for_timeout(400)
    assert page.locator("#themed-panel").evaluate(
        "element => getComputedStyle(element).backgroundColor"
    ) == ("rgb(25, 25, 25)")
