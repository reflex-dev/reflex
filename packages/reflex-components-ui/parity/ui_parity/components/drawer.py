"""The drawer: closed and open from each edge of the page, and how it is dismissed."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from playwright.sync_api import Locator, Page

import reflex as rx
from ui_parity.components.dialog import OPEN, close_dialog, open_dialog
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.look import Point, State
from ui_parity.matrix import DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import wait_for_text

DIRECTIONS = ["bottom", "top", "left", "right"]

# Where an app puts the panel of a drawer from each edge: the styles of the
# content, over the ones that stretch it over the page.
PLACES: dict[str, dict[str, str]] = {
    "bottom": {"top": "auto", "height": "40%"},
    "top": {"bottom": "auto", "height": "40%"},
    "left": {"right": "auto", "width": "20em"},
    "right": {"left": "auto", "width": "20em"},
}


def _panel(namespace: Any, direction: str, handle: bool = False, **props: Any) -> Any:
    """Create the content of a drawer from an edge.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        direction: The edge it comes from.
        handle: Whether it has a handle.
        **props: Further props of the content.

    Returns:
        The content: a title, a description and the button that closes it.
    """
    drawer = namespace.drawer
    return drawer.content(
        namespace.flex(
            *([drawer.handle()] if handle else []),
            drawer.title("Settings"),
            drawer.description("What the drawer is about."),
            drawer.close(namespace.button("Close")),
            direction="column",
            spacing="3",
            width="100%",
        ),
        padding="2em",
        background_color=rx.color("gray", 2),
        **PLACES[direction],
        **props,
    )


def _drawer(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a drawer and the button that opens it.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the root. ``handle`` asks for a handle in the
            drawer, ``overlay`` says whether it has an overlay, and
            ``inside`` puts the overlay in the portal, before the content.

    Returns:
        The drawer.
    """
    props = dict(props)
    drawer = namespace.drawer
    handle, overlay = props.pop("handle", False), props.pop("overlay", True)
    inside = props.pop("inside", False)
    content = _panel(namespace, props.get("direction", "bottom"), handle)
    shade = [drawer.overlay()] if overlay else []
    return drawer.root(
        drawer.trigger(namespace.button("Open")),
        *([] if inside else shade),
        drawer.portal(*(shade if inside else []), content),
        **props,
    )


def _close(page: Page, target: Locator, point: Point) -> None:
    """Close the open drawer, and wait until nothing of it is left to happen.

    Args:
        page: The page.
        target: The trigger.
        point: The middle of the trigger.
    """
    close_dialog(page, target, point)
    if not target.evaluate("trigger => trigger.hasAttribute('data-rx-dialog-trigger')"):
        # The drawer of Radix gives the page its scroll position back some
        # time after it has closed, which would move the page under the
        # next cell.
        page.wait_for_timeout(SETTLED)


# How long after it has closed the drawer of Radix still moves the page, in
# milliseconds.
SETTLED = 700

MATRIX = Matrix(
    component="drawer",
    render=_drawer,
    base={"direction": "bottom"},
    sweep={
        "direction": DIRECTIONS,
        "handle": [True],
        "overlay": [False],
        "inside": [True],
        "modal": [False],
        "appearance": [DARK],
        "state": [HOVER, FOCUS_VISIBLE, OPEN],
    },
    groups=[
        {"direction": DIRECTIONS, "state": [OPEN], "appearance": [LIGHT, DARK]},
        {"direction": DIRECTIONS, "handle": [True], "state": [OPEN]},
        {"overlay": [False], "state": [OPEN]},
        {"inside": [True], "state": [OPEN]},
    ],
    # As wide as the page, one frame under another: a drawer covers the
    # viewport, and is read in the frame the page is scrolled to.
    stage=(1200, 700),
    crop="stage",
    target="button",
    states={
        OPEN: State(enter=open_dialog, leave=_close, matches="[data-state='open']")
    },
    # Not held to zero. At a threshold of zero every cell but one is equal
    # pixel for pixel: the ring of the focus on the trigger, which the
    # browser anti-aliases by where the button is on the page, differs by 9
    # pixels of 840000.
    tolerance=0.00002,
)


class DrawerState(rx.State):
    """What the drawers of the contract are bound to."""

    shown: rx.Field[bool] = rx.field(False)
    kept: rx.Field[bool] = rx.field(False)
    seen: rx.Field[list[str]] = rx.field(default_factory=list)
    clicks: rx.Field[int] = rx.field(0)

    @rx.event
    def set_shown(self, value: bool):
        """Follow the bound drawer.

        Args:
            value: Whether it is open.
        """
        self.shown = value

    @rx.event
    def set_kept(self, value: bool):
        """Follow the drawer that is not dismissible.

        Args:
            value: Whether it is open.
        """
        self.kept = value

    @rx.event
    def see_open(self, value: bool):
        """Keep whether a drawer opened or closed.

        Args:
            value: Whether it is open.
        """
        self.seen.append("open" if value else "closed")

    @rx.event
    def see_moved(self, value: bool):
        """Keep that a drawer has slid in or out.

        Args:
            value: Whether it is open.
        """
        self.seen.append("in" if value else "out")

    @rx.event
    def see(self, what: str):
        """Keep what happened to a drawer.

        Args:
            what: The event.
        """
        self.seen.append(what)

    @rx.event
    def save(self):
        """Close the bound drawer from the backend."""
        self.shown = False

    @rx.event
    def click(self):
        """Count a click on the button beside the drawers."""
        self.clicks += 1


def _one(namespace: Any, name: str, direction: str = "bottom", **props: Any) -> Any:
    """Create a drawer whose parts are named after it.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        name: What the ids of its trigger, its panel and its close button
            start with.
        direction: The edge it comes from.
        **props: The props of the root. ``content`` holds the ones of the
            content, and ``field`` the ones of the input inside it.

    Returns:
        The drawer.
    """
    drawer = namespace.drawer
    content, field = props.pop("content", {}), props.pop("field", {})
    return drawer.root(
        drawer.trigger(namespace.button(name, id=f"{name}-open")),
        drawer.overlay(),
        drawer.portal(
            drawer.content(
                drawer.title(f"Drawer {name}"),
                drawer.description("What the drawer is about."),
                rx.el.input(id=f"{name}-input", **field),
                drawer.close(namespace.button("Close", id=f"{name}-close")),
                id=f"{name}-panel",
                background_color="white",
                padding="1em",
                **PLACES[direction],
                **content,
            )
        ),
        direction=direction,
        **props,
    )


def _contract(namespace: Any) -> Any:
    """Create what the contract page shows.

    Args:
        namespace: ``rx`` or ``rx.ui``.

    Returns:
        A drawer from each edge, one that says what happens to it, one that
        is not dismissible, one that is not modal and one bound to state.
    """
    return namespace.box(
        _one(
            namespace,
            "plain",
            on_open_change=DrawerState.see_open,
            on_animation_end=DrawerState.see_moved,
            content={
                "on_open_auto_focus": DrawerState.see("focus-in"),
                "on_close_auto_focus": DrawerState.see("focus-out"),
                "on_escape_key_down": DrawerState.see("escape"),
                "on_pointer_down_outside": DrawerState.see("outside"),
                "on_interact_outside": DrawerState.see("interact"),
            },
        ),
        *(_one(namespace, side, side) for side in ("top", "left", "right")),
        _one(
            namespace,
            "kept",
            dismissible=False,
            open=DrawerState.kept,
            on_open_change=DrawerState.set_kept,
            field={"on_click": DrawerState.set_kept(False)},
        ),
        _one(namespace, "beside", modal=False),
        _one(
            namespace,
            "bound",
            open=DrawerState.shown,
            on_open_change=DrawerState.set_shown,
            content={"on_click": DrawerState.save},
        ),
        rx.el.button("Show", id="show", on_click=DrawerState.set_shown(True)),
        rx.el.button("Behind", id="behind", on_click=DrawerState.click),
        rx.el.span(DrawerState.seen.to_string(), id="seen"),
        rx.el.span(DrawerState.shown.to_string(), id="shown"),
        rx.el.span(DrawerState.kept.to_string(), id="kept"),
        rx.el.span(DrawerState.clicks.to_string(), id="clicks"),
    )


CONTRACT = Contract(component="drawer", render=_contract)

# How long a drawer takes to slide in or out, and some more, in milliseconds.
MOVED = 700


def _open(run: Run, name: str) -> None:
    """Open a drawer from its trigger, and wait until it has slid in.

    Args:
        run: The run, on a page.
        name: What the ids of its parts start with.
    """
    run.page.locator(f"#{name}-open").click()
    run.page.locator(f"#{name}-panel").wait_for()
    run.page.wait_for_timeout(MOVED)


def _wait_for_closed(run: Run, name: str) -> None:
    """Wait until a drawer is closed.

    Args:
        run: The run, on a page.
        name: What the ids of its parts start with.
    """
    run.page.locator(f"#{name}-panel").wait_for(state="hidden")


def _wait_for_focus(run: Run, element: str) -> None:
    """Wait until an element has the focus.

    Args:
        run: The run, on a page.
        element: Its id.
    """
    run.page.wait_for_function("id => document.activeElement.id === id", arg=element)


@CONTRACT.step("its trigger is a button in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    trigger = run.server.element("plain-open")
    assert (trigger.tag, trigger.text, trigger.attributes["aria-haspopup"]) == (
        "button",
        "plain",
        "dialog",
    )


@CONTRACT.step("what it holds is in the server render", on=SERVER)
def _server_content(run: Run) -> None:
    assert run.server.element("plain-panel").text == (
        "Drawer plainWhat the drawer is about.Close"
    )


@CONTRACT.step("opens and closes with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    page = run.page
    page.set_default_timeout(3000)
    assert not page.locator("#plain-panel").is_visible()
    page.locator("#plain-open").click()
    page.wait_for_timeout(MOVED)
    assert page.locator("#plain-panel").is_visible()
    page.locator("#plain-close").click()
    page.wait_for_timeout(MOVED)
    assert not page.locator("#plain-panel").is_visible()


@CONTRACT.step("has the role, the name and the description of a dialog")
def _role(run: Run) -> None:
    page = run.page
    trigger = page.locator("#plain-open")
    assert trigger.get_attribute("aria-expanded") == "false"
    _open(run, "plain")
    assert trigger.get_attribute("aria-expanded") == "true"
    assert trigger.get_attribute("data-state") == "open"
    shown = page.get_by_role("dialog", name="Drawer plain")
    assert shown.count() == 1
    assert shown.evaluate(
        "dialog => document.getElementById(dialog.getAttribute('aria-describedby'))"
        ".textContent"
    ) == ("What the drawer is about.")


@CONTRACT.step("slides in from each edge of the page, and stops there")
def _edges(run: Run) -> None:
    page = run.page
    edges = {}
    for side in ("plain", "top", "left", "right"):
        _open(run, side)
        box = page.locator(f"#{side}-panel").bounding_box()
        assert box is not None
        edges[side] = [
            round(box["x"]),
            round(box["y"]),
            round(box["x"] + box["width"]),
            round(box["y"] + box["height"]),
        ]
        page.keyboard.press("Escape")
        _wait_for_closed(run, side)
    assert edges == {
        "plain": [0, 432, 1280, 720],
        "top": [0, 0, 1280, 288],
        "left": [0, 0, 320, 720],
        "right": [960, 0, 1280, 720],
    }


@CONTRACT.step("the focus moves into the drawer, and back to its trigger")
def _focus(run: Run) -> None:
    page = run.page
    page.locator("#plain-open").focus()
    page.keyboard.press("Enter")
    page.locator("#plain-panel").wait_for()
    page.wait_for_function(
        "document.getElementById('plain-panel').contains(document.activeElement)"
    )
    page.wait_for_timeout(MOVED)
    page.keyboard.press("Escape")
    _wait_for_closed(run, "plain")
    _wait_for_focus(run, "plain-open")


@CONTRACT.step("Tab does not reach the page behind an open drawer")
def _tab(run: Run) -> None:
    page = run.page
    _open(run, "plain")
    behind = []
    for _ in range(6):
        page.keyboard.press("Tab")
        behind.append(
            page.evaluate(
                "document.activeElement !== document.body"
                " && !document.getElementById('plain-panel')"
                ".contains(document.activeElement)"
            )
        )
    assert behind == [False] * 6


@CONTRACT.step("Escape, a press beside the panel and its button close it, and say so")
def _dismiss(run: Run) -> None:
    page = run.page
    _open(run, "plain")
    wait_for_text(page, "seen", '["open","focus-in","in"]')
    page.keyboard.press("Escape")
    _wait_for_closed(run, "plain")
    wait_for_text(
        page, "seen", '["open","focus-in","in","escape","closed","focus-out","out"]'
    )
    _open(run, "top")
    page.mouse.click(640, 600)
    _wait_for_closed(run, "top")
    _open(run, "top")
    page.locator("#top-close").click()
    _wait_for_closed(run, "top")


@CONTRACT.step("says that a press beside the panel dismissed it")
def _events_outside(run: Run) -> None:
    page = run.page
    _open(run, "plain")
    page.mouse.click(640, 100)
    _wait_for_closed(run, "plain")
    wait_for_text(
        page,
        "seen",
        '["open","focus-in","in","outside","interact","closed","focus-out","out"]',
    )


@CONTRACT.step("the page behind an open drawer takes no click")
def _modal(run: Run) -> None:
    page = run.page
    box = page.locator("#behind").bounding_box()
    assert box is not None
    _open(run, "left")
    page.mouse.click(box["x"] + box["width"] / 2 + 400, box["y"] + box["height"] / 2)
    _wait_for_closed(run, "left")
    page.wait_for_timeout(300)
    assert page.locator("#clicks").text_content() == "0"


@CONTRACT.step("a drawer that is not dismissible is closed by its state alone")
def _kept(run: Run) -> None:
    page = run.page
    _open(run, "kept")
    wait_for_text(page, "kept", "true")
    page.keyboard.press("Escape")
    page.mouse.click(640, 100)
    page.locator("#kept-close").click()
    page.wait_for_timeout(MOVED)
    assert page.locator("#kept-panel").is_visible()
    assert page.locator("#kept").text_content() == "true"
    page.locator("#kept-input").click()
    _wait_for_closed(run, "kept")
    wait_for_text(page, "kept", "false")


@CONTRACT.step("a drawer that is not modal leaves the page beside it as it is")
def _beside(run: Run) -> None:
    page = run.page
    _open(run, "beside")
    page.locator("#behind").click()
    wait_for_text(page, "clicks", "1")
    assert page.locator("#beside-panel").is_visible()
    page.locator("#beside-close").click()
    _wait_for_closed(run, "beside")


@CONTRACT.step("a drawer bound to state follows it, and is closed from the backend")
def _bound(run: Run) -> None:
    page = run.page
    page.locator("#show").click()
    page.locator("#bound-panel").wait_for()
    wait_for_text(page, "shown", "true")
    page.wait_for_timeout(MOVED)
    page.locator("#bound-panel").click(position={"x": 400, "y": 10})
    _wait_for_closed(run, "bound")
    wait_for_text(page, "shown", "false")
    _open(run, "bound")
    wait_for_text(page, "shown", "true")
    page.keyboard.press("Escape")
    _wait_for_closed(run, "bound")
    wait_for_text(page, "shown", "false")


@CONTRACT.step("is dragged out of the page by its panel")
def _drag(run: Run) -> None:
    page = run.page
    _open(run, "plain")
    page.mouse.move(640, 450)
    page.mouse.down()
    for y in range(460, 700, 20):
        page.mouse.move(640, y)
    page.mouse.up()
    _wait_for_closed(run, "plain")
