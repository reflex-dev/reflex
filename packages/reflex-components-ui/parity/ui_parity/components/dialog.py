"""The dialog: closed and open in every size, over the page, and how it is dismissed."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from playwright.sync_api import Locator, Page

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.look import Point, State
from ui_parity.matrix import DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import PARAGRAPH, focused, wait_for_text

SIZES = ["1", "2", "3", "4"]
OPEN = "open"
# A dialog that is open, in either system.
SHOWN = "[role=dialog]:visible, [role=alertdialog]:visible, dialog[open]"


def body(namespace: Any, kind: Any, long: bool = False) -> list[Any]:
    """Create what a dialog of a matrix holds.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        kind: The namespace of the dialog.
        long: Whether it holds more than the viewport has room for.

    Returns:
        A title, a description, and the buttons that close the dialog.
    """
    closes = getattr(kind, "close", None) or kind.cancel
    return [
        kind.title("Edit profile"),
        kind.description("Make changes to your profile."),
        *(rx.el.p(f"{number}. {PARAGRAPH}") for number in range(1, 40 if long else 1)),
        namespace.flex(
            closes(namespace.button("Cancel", variant="soft", color_scheme="gray")),
            closes(namespace.button("Save")),
            spacing="3",
            justify="end",
            margin_top="16px",
        ),
    ]


def _dialog(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a dialog and the button that opens it.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the content. ``long`` asks for more than the
            viewport has room for, ``themed`` for a theme of another accent
            and radius around the dialog, and ``variant`` is the
            one of the button that opens it.

    Returns:
        The dialog.
    """
    props = dict(props)
    dialog = namespace.dialog
    long, themed = props.pop("long", False), props.pop("themed", False)
    shown = dialog.root(
        dialog.trigger(namespace.button("Open", variant=props.pop("variant", "solid"))),
        dialog.content(*body(namespace, dialog, long), **props),
    )
    if themed:
        return namespace.theme(shown, accent_color="ruby", radius="full")
    return shown


def open_dialog(page: Page, target: Locator, point: Point) -> None:
    """Open a dialog from its trigger, and wait for it.

    Args:
        page: The page.
        target: The trigger.
        point: The middle of the trigger.
    """
    target.click()
    page.locator(SHOWN).first.wait_for()
    # The pointer is not left on the trigger, nor on a button of the dialog.
    page.mouse.move(1, 1)


def close_dialog(page: Page, target: Locator, point: Point) -> None:
    """Close the open dialog, and take the focus off its trigger.

    Args:
        page: The page.
        target: The trigger.
        point: The middle of the trigger.
    """
    page.keyboard.press("Escape")
    page.locator(SHOWN).first.wait_for(state="detached")
    # The trigger has the focus back before it loses it: a focus that came
    # back later would scroll the page to the trigger under the next cell.
    target.evaluate(
        "trigger => new Promise(done => {"
        " const wait = () => document.activeElement === trigger"
        " ? done(trigger.blur()) : requestAnimationFrame(wait); wait(); })"
    )


OPENED = State(enter=open_dialog, leave=close_dialog, matches="[data-state='open']")

MATRIX = Matrix(
    component="dialog",
    render=_dialog,
    sweep={
        "size": SIZES,
        "long": [True],
        "themed": [True],
        "max_width": ["450px"],
        "variant": ["soft", "classic", "surface"],
        "appearance": [DARK],
        "state": [HOVER, FOCUS_VISIBLE, OPEN],
    },
    groups=[
        {"size": SIZES, "state": [OPEN], "appearance": [LIGHT, DARK]},
        {"long": [True], "size": ["1", "4"], "state": [OPEN]},
        {"themed": [True], "state": [OPEN], "appearance": [LIGHT, DARK]},
        {"max_width": ["450px"], "state": [OPEN]},
        {
            "variant": ["soft", "classic", "surface", "ghost", "outline"],
            "state": [OPEN],
        },
    ],
    # As wide as the page, one frame under another: a dialog covers the
    # viewport, and is read in the frame the page is scrolled to.
    stage=(1200, 700),
    crop="stage",
    target="button",
    states={OPEN: OPENED},
    # Not held to zero. At a threshold of zero every cell but two is equal
    # pixel for pixel: the ring of the focus on the trigger, which the
    # browser anti-aliases by where the button is on the page, differs by 9
    # pixels of 840000, and by 6 at the default threshold.
    tolerance=0.00002,
)


class DialogState(rx.State):
    """What the dialogs of the contract are bound to."""

    shown: rx.Field[bool] = rx.field(False)
    seen: rx.Field[list[str]] = rx.field(default_factory=list)
    clicks: rx.Field[int] = rx.field(0)

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
    def save(self):
        """Close the bound dialog from the backend."""
        self.shown = False

    @rx.event
    def click(self):
        """Count a click on the button behind the dialogs."""
        self.clicks += 1


def _contract(namespace: Any) -> Any:
    """Create what the contract page shows.

    Args:
        namespace: ``rx`` or ``rx.ui``.

    Returns:
        A dialog that says what happens to it, one bound to state, one with
        a dialog and a select inside it, and one in a theme of its own.
    """
    dialog, button = namespace.dialog, namespace.button
    return namespace.box(
        dialog.root(
            dialog.trigger(button("Open", id="open")),
            dialog.content(
                dialog.title("Edit profile"),
                dialog.description("Make changes to your profile."),
                rx.el.input(id="name"),
                dialog.close(button("Close", id="close")),
                id="panel",
                on_open_auto_focus=DialogState.see("focus-in"),
                on_close_auto_focus=DialogState.see("focus-out"),
                on_escape_key_down=DialogState.see("escape"),
                on_pointer_down_outside=DialogState.see("outside"),
                on_interact_outside=DialogState.see("interact"),
            ),
            on_open_change=DialogState.see_open,
        ),
        dialog.root(
            dialog.trigger(button("Bound", id="bound-open")),
            dialog.content(
                dialog.title("Bound"),
                button("Save", id="save", on_click=DialogState.save),
                id="bound-panel",
            ),
            open=DialogState.shown,
            on_open_change=DialogState.set_shown,
        ),
        dialog.root(
            dialog.trigger(button("Outer", id="outer-open")),
            dialog.content(
                dialog.title("Outer"),
                namespace.select(
                    ["Small", "Large"],
                    default_value="Small",
                    id="pick",
                    position="popper",
                ),
                dialog.root(
                    dialog.trigger(button("Inner", id="inner-open")),
                    dialog.content(
                        dialog.title("Inner"),
                        dialog.close(button("Back", id="inner-close")),
                        id="inner-panel",
                    ),
                ),
                dialog.close(button("Done", id="outer-close")),
                id="outer-panel",
            ),
        ),
        namespace.theme(
            dialog.root(
                dialog.trigger(button("Themed", id="themed-open")),
                dialog.content(
                    dialog.title("Themed"),
                    dialog.close(button("Fine", id="themed-close")),
                    id="themed-panel",
                ),
            ),
            accent_color="ruby",
            appearance="dark",
        ),
        rx.el.button("Show", id="show", on_click=DialogState.set_shown(True)),
        rx.el.button("Behind", id="behind", on_click=DialogState.click),
        rx.el.span(DialogState.seen.to_string(), id="seen"),
        rx.el.span(DialogState.shown.to_string(), id="shown"),
        rx.el.span(DialogState.clicks.to_string(), id="clicks"),
    )


CONTRACT = Contract(component="dialog", render=_contract)

# The properties of the panel of a dialog a step reads.
BOX = (
    "position",
    "box-sizing",
    "width",
    "max-width",
    "padding-top",
    "padding-left",
    "border-top-left-radius",
    "background-color",
    "overflow-y",
    "outline-style",
    "opacity",
    "transform",
)


def _open(run: Run, trigger: str, panel: str) -> None:
    """Open a dialog from its trigger, and wait for its panel.

    Args:
        run: The run, on a page.
        trigger: The id of the trigger.
        panel: The id of the panel.
    """
    run.page.locator(f"#{trigger}").click()
    run.page.locator(f"#{panel}").wait_for()


def _wait_for_closed(run: Run, panel: str) -> None:
    """Wait until a dialog is closed.

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
        "Open",
        "dialog",
    )


@CONTRACT.step("what it holds is in the server render", on=SERVER)
def _server_content(run: Run) -> None:
    assert run.server.element("panel").text == (
        "Edit profileMake changes to your profile.Close"
    )


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


@CONTRACT.step("has the role, the name and the description of a dialog")
def _role(run: Run) -> None:
    page = run.page
    trigger = page.locator("#open")
    assert trigger.get_attribute("aria-expanded") == "false"
    assert trigger.get_attribute("data-state") == "closed"
    _open(run, "open", "panel")
    assert trigger.get_attribute("aria-expanded") == "true"
    assert trigger.get_attribute("data-state") == "open"
    shown = page.get_by_role("dialog", name="Edit profile")
    assert shown.count() == 1
    assert shown.evaluate(
        "dialog => document.getElementById(dialog.getAttribute('aria-describedby'))"
        ".textContent"
    ) == ("Make changes to your profile.")
    assert shown.get_by_role("heading", name="Edit profile").count() == 1


@CONTRACT.step("the panel has the box of a dialog of the third size")
def _box(run: Run) -> None:
    _open(run, "open", "panel")
    run.page.wait_for_timeout(400)
    assert run.page.locator("#panel").evaluate(
        "(panel, names) => names.map(name => getComputedStyle(panel)"
        ".getPropertyValue(name))",
        list(BOX),
    ) == [
        "relative",
        "border-box",
        "600px",
        "600px",
        "24px",
        "24px",
        "12px",
        "rgb(255, 255, 255)",
        "auto",
        "none",
        "1",
        "none",
    ]


@CONTRACT.step("the focus moves into the dialog, and back to its trigger")
def _focus(run: Run) -> None:
    page = run.page
    page.locator("#open").focus()
    page.keyboard.press("Enter")
    page.locator("#panel").wait_for()
    _wait_for_focus(run, "name")
    page.keyboard.press("Escape")
    _wait_for_closed(run, "panel")
    _wait_for_focus(run, "open")
    page.keyboard.press("Space")
    page.locator("#panel").wait_for()
    page.locator("#close").click()
    _wait_for_closed(run, "panel")
    _wait_for_focus(run, "open")


@CONTRACT.step("Tab stays inside an open dialog")
def _tab(run: Run) -> None:
    page = run.page
    _open(run, "open", "panel")
    stops = []
    for _ in range(5):
        page.keyboard.press("Tab")
        stops.append(focused(page))
    assert stops == ["close", "name", "close", "name", "close"]
    page.keyboard.press("Shift+Tab")
    assert focused(page) == "name"


@CONTRACT.step("a press beside the panel closes the dialog")
def _outside(run: Run) -> None:
    page = run.page
    _open(run, "open", "panel")
    page.locator("#panel").click(position={"x": 5, "y": 5})
    page.wait_for_timeout(200)
    assert page.locator("#panel").is_visible()
    page.mouse.click(5, 5)
    _wait_for_closed(run, "panel")


@CONTRACT.step("the page behind an open dialog takes no click")
def _modal(run: Run) -> None:
    page = run.page
    box = page.locator("#behind").bounding_box()
    assert box is not None
    _open(run, "open", "panel")
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    _wait_for_closed(run, "panel")
    page.wait_for_timeout(300)
    assert page.locator("#clicks").text_content() == "0"


@CONTRACT.step("says when it opens and closes, and what dismissed it")
def _events(run: Run) -> None:
    page = run.page
    _open(run, "open", "panel")
    wait_for_text(page, "seen", '["open","focus-in"]')
    page.keyboard.press("Escape")
    _wait_for_closed(run, "panel")
    wait_for_text(page, "seen", '["open","focus-in","escape","closed","focus-out"]')


@CONTRACT.step("says that a press beside the panel dismissed it")
def _events_outside(run: Run) -> None:
    page = run.page
    _open(run, "open", "panel")
    page.mouse.click(5, 5)
    _wait_for_closed(run, "panel")
    wait_for_text(
        page,
        "seen",
        '["open","focus-in","outside","interact","closed","focus-out"]',
    )


@CONTRACT.step("a dialog in a dialog opens over it, and Escape closes the topmost")
def _nested(run: Run) -> None:
    page = run.page
    _open(run, "outer-open", "outer-panel")
    _open(run, "inner-open", "inner-panel")
    # Once the focus is in the dialog it is the topmost, to both systems.
    _wait_for_focus(run, "inner-close")
    page.locator("#outer-panel").wait_for()
    page.keyboard.press("Escape")
    _wait_for_closed(run, "inner-panel")
    page.locator("#outer-panel").wait_for()
    _wait_for_focus(run, "inner-open")
    _open(run, "inner-open", "inner-panel")
    # Once the focus is in the dialog it is the topmost, to both systems.
    _wait_for_focus(run, "inner-close")
    page.locator("#inner-close").click()
    _wait_for_closed(run, "inner-panel")
    page.locator("#outer-panel").wait_for()
    page.keyboard.press("Escape")
    _wait_for_closed(run, "outer-panel")
    _wait_for_focus(run, "outer-open")


@CONTRACT.step("a select in a dialog opens over it and chooses")
def _select(run: Run) -> None:
    page = run.page
    _open(run, "outer-open", "outer-panel")
    page.locator("#pick").focus()
    page.keyboard.press("Enter")
    page.get_by_role("option", name="Large").wait_for()
    page.wait_for_function("document.activeElement.getAttribute('role') === 'option'")
    page.keyboard.press("ArrowDown")
    page.wait_for_function("document.activeElement.textContent === 'Large'")
    page.keyboard.press("Enter")
    wait_for_text(page, "pick", "Large")
    page.get_by_role("option", name="Large").wait_for(state="hidden")
    page.locator("#outer-panel").wait_for()
    page.locator("#pick").focus()
    page.keyboard.press("Enter")
    page.get_by_role("option", name="Large").wait_for()
    page.keyboard.press("Escape")
    page.get_by_role("option", name="Large").wait_for(state="hidden")
    page.locator("#outer-panel").wait_for()


@CONTRACT.step("a dialog bound to state follows it, and is closed from the backend")
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


@CONTRACT.step("the accent of a theme around a dialog reaches what it holds")
def _themed(run: Run) -> None:
    page = run.page
    _open(run, "themed-open", "themed-panel")
    page.mouse.move(1, 1)
    page.wait_for_timeout(400)
    assert page.locator("#themed-close").evaluate(
        "element => getComputedStyle(element).backgroundColor"
    ) == ("rgb(229, 70, 102)")


@CONTRACT.step("the dark appearance of a theme around a dialog reaches its panel")
def _themed_dark(run: Run) -> None:
    page = run.page
    _open(run, "themed-open", "themed-panel")
    page.wait_for_timeout(400)
    assert page.locator("#themed-panel").evaluate(
        "element => getComputedStyle(element).backgroundColor"
    ) == ("rgb(25, 25, 25)")
