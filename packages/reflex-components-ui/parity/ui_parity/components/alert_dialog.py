"""The alert dialog: closed and open in every size, and what does not dismiss it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.components.dialog import OPEN, OPENED, body
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import focused, wait_for_text

SIZES = ["1", "2", "3", "4"]


def _alert(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create an alert dialog and the button that opens it.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the content. ``long`` asks for more than the
            viewport has room for, and ``themed`` for a theme of another
            accent and radius around the dialog.

    Returns:
        The alert dialog.
    """
    props = dict(props)
    alert = namespace.alert_dialog
    long, themed = props.pop("long", False), props.pop("themed", False)
    shown = alert.root(
        alert.trigger(namespace.button("Delete", color_scheme="red")),
        alert.content(*body(namespace, alert, long), **props),
    )
    if themed:
        return namespace.theme(shown, accent_color="ruby", radius="full")
    return shown


MATRIX = Matrix(
    component="alert_dialog",
    render=_alert,
    sweep={
        "size": SIZES,
        "long": [True],
        "themed": [True],
        "max_width": ["450px"],
        "appearance": [DARK],
        "state": [HOVER, FOCUS_VISIBLE, OPEN],
    },
    groups=[
        {"size": SIZES, "state": [OPEN], "appearance": [LIGHT, DARK]},
        {"long": [True], "size": ["1", "4"], "state": [OPEN]},
        {"themed": [True], "state": [OPEN], "appearance": [LIGHT, DARK]},
        {"max_width": ["450px"], "state": [OPEN]},
    ],
    # As wide as the page, one frame under another: a dialog covers the
    # viewport, and is read in the frame the page is scrolled to.
    stage=(1200, 700),
    crop="stage",
    target="button",
    states={OPEN: OPENED},
    # Not held to zero. At a threshold of zero every cell but one is equal
    # pixel for pixel: the ring of the focus on the trigger, which the
    # browser anti-aliases by where the button is on the page, differs by 9
    # pixels of 840000.
    tolerance=0.00002,
)


class AlertDialogState(rx.State):
    """What the alert dialogs of the contract are bound to."""

    shown: rx.Field[bool] = rx.field(False)
    seen: rx.Field[list[str]] = rx.field(default_factory=list)

    @rx.event
    def set_shown(self, value: bool):
        """Follow the bound dialog.

        Args:
            value: Whether it is open.
        """
        self.shown = value

    @rx.event
    def see_open(self, value: bool):
        """Keep whether a dialog opened or closed.

        Args:
            value: Whether it is open.
        """
        self.seen.append("open" if value else "closed")

    @rx.event
    def see(self, what: str):
        """Keep what happened to a dialog.

        Args:
            what: The event.
        """
        self.seen.append(what)

    @rx.event
    def confirm(self):
        """Close the bound dialog from the backend."""
        self.shown = False


def _contract(namespace: Any) -> Any:
    """Create what the contract page shows.

    Args:
        namespace: ``rx`` or ``rx.ui``.

    Returns:
        An alert dialog that says what happens to it, whose action is
        before what cancels it, and one bound to state.
    """
    alert, button = namespace.alert_dialog, namespace.button
    return namespace.box(
        alert.root(
            alert.trigger(button("Delete", id="open")),
            alert.content(
                alert.title("Delete the file"),
                alert.description("It cannot be brought back."),
                alert.action(button("Delete it", id="action")),
                alert.cancel(button("Keep it", id="cancel")),
                id="panel",
                on_open_auto_focus=AlertDialogState.see("focus-in"),
                on_close_auto_focus=AlertDialogState.see("focus-out"),
                on_escape_key_down=AlertDialogState.see("escape"),
            ),
            on_open_change=AlertDialogState.see_open,
        ),
        alert.root(
            alert.trigger(button("Bound", id="bound-open")),
            alert.content(
                alert.title("Bound"),
                button("Confirm", id="confirm", on_click=AlertDialogState.confirm),
                id="bound-panel",
            ),
            open=AlertDialogState.shown,
            on_open_change=AlertDialogState.set_shown,
        ),
        rx.el.button("Show", id="show", on_click=AlertDialogState.set_shown(True)),
        rx.el.span(AlertDialogState.seen.to_string(), id="seen"),
        rx.el.span(AlertDialogState.shown.to_string(), id="shown"),
    )


CONTRACT = Contract(component="alert_dialog", render=_contract)


def _open(run: Run, trigger: str = "open", panel: str = "panel") -> None:
    """Open an alert dialog from its trigger, and wait for its panel.

    Args:
        run: The run, on a page.
        trigger: The id of the trigger.
        panel: The id of the panel.
    """
    run.page.locator(f"#{trigger}").click()
    run.page.locator(f"#{panel}").wait_for()


def _wait_for_closed(run: Run, panel: str = "panel") -> None:
    """Wait until an alert dialog is closed.

    Args:
        run: The run, on a page.
        panel: The id of its panel.
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
        "Delete",
        "dialog",
    )


@CONTRACT.step("what it holds is in the server render", on=SERVER)
def _server_content(run: Run) -> None:
    assert run.server.element("panel").text == (
        "Delete the fileIt cannot be brought back.Delete itKeep it"
    )


@CONTRACT.step("opens and closes with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    page = run.page
    page.set_default_timeout(3000)
    assert not page.locator("#panel").is_visible()
    page.locator("#open").click()
    page.wait_for_timeout(300)
    assert page.locator("#panel").is_visible()
    page.locator("#cancel").click()
    page.wait_for_timeout(300)
    assert not page.locator("#panel").is_visible()


@CONTRACT.step("has the role, the name and the description of an alert dialog")
def _role(run: Run) -> None:
    page = run.page
    trigger = page.locator("#open")
    assert trigger.get_attribute("aria-expanded") == "false"
    _open(run)
    assert trigger.get_attribute("aria-expanded") == "true"
    assert trigger.get_attribute("data-state") == "open"
    shown = page.get_by_role("alertdialog", name="Delete the file")
    assert shown.count() == 1
    assert shown.evaluate(
        "dialog => document.getElementById(dialog.getAttribute('aria-describedby'))"
        ".textContent"
    ) == ("It cannot be brought back.")


@CONTRACT.step("the focus moves to what cancels it, and back to its trigger")
def _focus(run: Run) -> None:
    page = run.page
    page.locator("#open").focus()
    page.keyboard.press("Enter")
    page.locator("#panel").wait_for()
    _wait_for_focus(run, "cancel")
    page.keyboard.press("Enter")
    _wait_for_closed(run)
    _wait_for_focus(run, "open")
    page.keyboard.press("Space")
    page.locator("#panel").wait_for()
    page.locator("#action").click()
    _wait_for_closed(run)
    _wait_for_focus(run, "open")


@CONTRACT.step("Tab stays inside an open alert dialog")
def _tab(run: Run) -> None:
    page = run.page
    _open(run)
    _wait_for_focus(run, "cancel")
    stops = []
    for _ in range(4):
        page.keyboard.press("Tab")
        stops.append(focused(page))
    assert stops == ["action", "cancel", "action", "cancel"]


@CONTRACT.step("a press beside the panel does not close it, and Escape does")
def _outside(run: Run) -> None:
    page = run.page
    _open(run)
    page.mouse.click(5, 5)
    page.mouse.click(640, 700)
    page.wait_for_timeout(300)
    assert page.locator("#panel").is_visible()
    page.keyboard.press("Escape")
    _wait_for_closed(run)
    wait_for_text(page, "seen", '["open","focus-in","escape","closed","focus-out"]')


@CONTRACT.step("its action and what cancels it close it, and say so")
def _close(run: Run) -> None:
    page = run.page
    _open(run)
    page.locator("#action").click()
    _wait_for_closed(run)
    _open(run)
    page.locator("#cancel").click()
    _wait_for_closed(run)
    wait_for_text(
        page,
        "seen",
        '["open","focus-in","closed","focus-out","open","focus-in","closed","focus-out"]',
    )


@CONTRACT.step(
    "an alert dialog bound to state follows it, and is closed from the backend"
)
def _bound(run: Run) -> None:
    page = run.page
    page.locator("#show").click()
    page.locator("#bound-panel").wait_for()
    wait_for_text(page, "shown", "true")
    page.locator("#confirm").click()
    _wait_for_closed(run, "bound-panel")
    wait_for_text(page, "shown", "false")
    _open(run, "bound-open", "bound-panel")
    wait_for_text(page, "shown", "true")
    page.keyboard.press("Escape")
    _wait_for_closed(run, "bound-panel")
    wait_for_text(page, "shown", "false")
