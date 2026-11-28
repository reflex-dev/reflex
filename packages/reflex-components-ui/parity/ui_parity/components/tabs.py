"""The tabs: both sizes and orientations, every state of a trigger, and the keys."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import focused, wait_for_text

SIZES = ["1", "2"]
ORIENTATIONS = ["horizontal", "vertical"]
RESPONSIVE = {"responsive": rx.breakpoints(initial="1", md="2")}
NAMES = ("Account", "Documents", "Settings")
MANY = tuple(f"Chapter {number}" for number in range(1, 13))


def _tabs(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create tabs.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the root. ``size`` is the one of the list,
            ``color_scheme`` the one of every trigger, ``disabled`` says
            that the last trigger is, and ``many`` asks for more triggers
            than the list has room for.

    Returns:
        The tabs.
    """
    props = dict(props)
    tabs = namespace.tabs
    names = MANY if props.pop("many", False) else NAMES
    disabled = props.pop("disabled", False)
    trigger = {
        key: props.pop(key) for key in ("color_scheme",) if props.get(key) is not None
    }
    props.pop("color_scheme", None)
    size = props.pop("size", None)
    return tabs.root(
        tabs.list(
            *(
                tabs.trigger(
                    name,
                    value=name.lower(),
                    **trigger,
                    **({"disabled": True} if disabled and name == names[-1] else {}),
                )
                for name in names
            ),
            **({} if size is None else {"size": size}),
        ),
        *(tabs.content(f"What is under {name}.", value=name.lower()) for name in names),
        **props,
    )


MATRIX = Matrix(
    component="tabs",
    render=_tabs,
    base={"default_value": "account"},
    cross={"size": SIZES, "orientation": ORIENTATIONS},
    sweep={
        "default_value": {"second": "documents", "none": None},
        "color_scheme": ["ruby", "gray", "yellow", "indigo"],
        "disabled": [True],
        "many": [True],
        "dir": ["rtl"],
        "size": RESPONSIVE,
        "appearance": [DARK],
        "state": [HOVER, FOCUS_VISIBLE],
        "viewport": [520],
    },
    groups=[
        {
            "default_value": {"second": "documents"},
            "state": [HOVER, FOCUS_VISIBLE],
            "appearance": [LIGHT, DARK],
        },
        {"size": SIZES, "state": [HOVER, FOCUS_VISIBLE], "appearance": [LIGHT, DARK]},
        {
            "orientation": ["vertical"],
            "default_value": {"second": "documents"},
            "state": [HOVER, FOCUS_VISIBLE],
        },
        {"color_scheme": ["ruby", "gray"], "appearance": [DARK]},
        {"dir": ["rtl"], "orientation": ORIENTATIONS, "size": SIZES},
        {"many": [True], "orientation": ORIENTATIONS},
        {"disabled": [True], "appearance": [LIGHT, DARK]},
        {"size": RESPONSIVE, "viewport": [520, 800, 1100]},
    ],
    stage=(360, 180),
    crop="stage",
    target="[role=tab]:nth-of-type(2)",
    parts={
        "root": ":scope > div",
        "list": "[role=tablist]",
        "selected": "[role=tab][aria-selected=true]",
        "text": "[role=tab]:nth-of-type(2) > span:first-child",
        "room": "[role=tab]:nth-of-type(2) > span:last-child",
        "last": "[role=tab]:last-child",
        "panel": "[role=tabpanel]:not([hidden])",
    },
    threshold=0,
    tolerance=0,
)


class TabsState(rx.State):
    """What the tabs of the contract are bound to."""

    bound: rx.Field[str] = rx.field("b")
    seen: rx.Field[list[str]] = rx.field(default_factory=list)

    @rx.event
    def set_bound(self, value: str):
        """Follow the bound tabs.

        Args:
            value: The value of the selected tab.
        """
        self.bound = value

    @rx.event
    def see(self, value: str):
        """Keep what a change handed over.

        Args:
            value: The value of the selected tab.
        """
        self.seen.append(value)

    @rx.event
    def pick_last(self):
        """Change the bound value from outside the tabs."""
        self.bound = "c"


def _letters(namespace: Any, name: str, off: str = "", **props: Any) -> Any:
    """Create tabs of a few letters, in a frame.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        name: The id of the frame. The id of a trigger is the name and its
            letter, as the id of a panel after ``panel``.
        off: The letter of a disabled tab.
        **props: The props of the root. ``loop`` is the one of the list.

    Returns:
        The frame.
    """
    tabs = namespace.tabs
    letters = "abc" if not off else "abcd"
    listed = {"loop": props.pop("loop")} if "loop" in props else {}
    return rx.el.div(
        tabs.root(
            tabs.list(
                *(
                    tabs.trigger(
                        letter.upper(),
                        value=letter,
                        id=f"{name}-{letter}",
                        **({"disabled": True} if letter == off else {}),
                    )
                    for letter in letters
                ),
                **listed,
            ),
            *(
                tabs.content(
                    f"Panel {letter}", value=letter, id=f"{name}-panel-{letter}"
                )
                for letter in letters
            ),
            **props,
        ),
        id=name,
    )


CONTRACT = Contract(
    component="tabs",
    render=lambda namespace: namespace.box(
        _letters(
            namespace, "plain", off="c", default_value="a", on_change=TabsState.see
        ),
        _letters(namespace, "upright", default_value="a", orientation="vertical"),
        _letters(namespace, "rtl", default_value="a", dir="rtl"),
        _letters(namespace, "manual", default_value="a", activation_mode="manual"),
        _letters(namespace, "ends", default_value="a", loop=False),
        _letters(
            namespace, "bound", value=TabsState.bound, on_change=TabsState.set_bound
        ),
        _letters(namespace, "none"),
        rx.el.div(
            namespace.tabs.root(
                namespace.tabs.list(namespace.tabs.trigger("Only", value="only")),
                namespace.tabs.content("The only panel", value="only"),
                default_value="only",
            ),
            id="bare",
        ),
        rx.el.button("Last", id="last", on_click=TabsState.pick_last),
        rx.el.span(TabsState.seen.to_string(), id="seen"),
        rx.el.span(TabsState.bound, id="bound-value"),
    ),
)

# The letters of the selected triggers of tabs and the text of the panels
# they show, by the id of their frame.
SHOWN = (
    "id => [[...document.getElementById(id).querySelectorAll("
    "'[role=tab][aria-selected=true]')].map(tab => tab.id).join(),"
    " [...document.getElementById(id).querySelectorAll('[role=tabpanel]')]"
    ".filter(panel => panel.checkVisibility()).map(panel => panel.textContent).join()]"
)
# How long a key is held, in milliseconds.
HELD = 60


def _wait_for_shown(run: Run, name: str, letter: str) -> None:
    """Wait until tabs have one tab selected, and show its panel alone.

    Args:
        run: The run, on a page.
        name: The id of the frame of the tabs.
        letter: The letter of the tab, or nothing when none is selected.
    """
    expected = [f"{name}-{letter}", f"Panel {letter}"] if letter else ["", ""]
    run.page.wait_for_function(
        f"([id, shown]) => JSON.stringify(({SHOWN})(id)) === JSON.stringify(shown)",
        arg=[name, expected],
    )


def _press(run: Run, key: str, lands: str) -> None:
    """Press a key, and wait for the focus to be where it leads.

    Args:
        run: The run, on a page.
        key: The key.
        lands: The id of the element that then has the focus.
    """
    run.page.keyboard.press(key, delay=HELD)
    run.page.wait_for_function("id => document.activeElement.id === id", arg=lands)


@CONTRACT.step("the selected tab and its panel are in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    tab = run.server.element("plain-a")
    assert (tab.tag, tab.attributes["role"], tab.attributes["aria-selected"]) == (
        "button",
        "tab",
        "true",
    )
    assert run.server.element("plain-b").attributes["aria-selected"] == "false"
    assert run.server.element("plain-panel-a").text == "Panel a"
    assert run.server.element("bound-panel-b").text == "Panel b"


@CONTRACT.step(
    "shows the panel it starts with, with JavaScript disabled", on=NO_JAVASCRIPT
)
def _without_javascript(run: Run) -> None:
    run.page.set_default_timeout(3000)
    _wait_for_shown(run, "plain", "a")
    _wait_for_shown(run, "bound", "b")
    _wait_for_shown(run, "none", "")


@CONTRACT.step("has the roles, the names and the states of tabs")
def _role(run: Run) -> None:
    page = run.page
    assert page.get_by_role("tablist").count() == 8
    plain = page.locator("#plain")
    assert (
        plain.get_by_role("tablist").get_attribute("aria-orientation") == "horizontal"
    )
    assert (
        page
        .locator("#upright")
        .get_by_role("tablist")
        .get_attribute("aria-orientation")
        == "vertical"
    )
    assert plain.get_by_role("tab").all_text_contents() == ["AA", "BB", "CC", "DD"]
    assert plain.get_by_role("tab", selected=True).all_text_contents() == ["AA"]
    assert plain.get_by_role("tab", disabled=True).all_text_contents() == ["CC"]
    panel = plain.get_by_role("tabpanel")
    assert panel.count() == 1
    bare = page.locator("#bare")
    tab, panel = bare.get_by_role("tab", selected=True), bare.get_by_role("tabpanel")
    assert tab.get_attribute("aria-controls") == panel.get_attribute("id")
    assert panel.get_attribute("aria-labelledby") == tab.get_attribute("id")
    assert bare.get_by_role("tabpanel", name="Only").text_content() == (
        "The only panel"
    )


@CONTRACT.step("a trigger and a panel given ids of their own name each other")
def _ids(run: Run) -> None:
    plain = run.page.locator("#plain")
    assert run.page.locator("#plain-a").get_attribute("aria-controls") == (
        "plain-panel-a"
    )
    assert plain.get_by_role("tabpanel", name="A").text_content() == "Panel a"


@CONTRACT.step("Tab stops on the selected trigger, then on its panel")
def _tab(run: Run) -> None:
    page = run.page
    stops = []
    for _ in range(4):
        page.keyboard.press("Tab")
        stops.append(focused(page))
    assert stops == ["plain-a", "plain-panel-a", "upright-a", "upright-panel-a"]
    page.locator("#plain-d").click()
    _wait_for_shown(run, "plain", "d")
    page.locator("#upright-a").focus()
    for stop in ("plain-panel-d", "plain-d"):
        page.keyboard.press("Shift+Tab")
        assert focused(page) == stop


@CONTRACT.step(
    "the arrow keys, Home and End select the tabs that can be, around the ends"
)
def _arrows(run: Run) -> None:
    page = run.page
    page.locator("#plain-a").focus()
    for key, letter in (
        ("ArrowRight", "b"),
        ("ArrowRight", "d"),
        ("ArrowRight", "a"),
        ("ArrowLeft", "d"),
        ("ArrowLeft", "b"),
        ("End", "d"),
        ("Home", "a"),
    ):
        _press(run, key, f"plain-{letter}")
        _wait_for_shown(run, "plain", letter)
    for key in ("ArrowDown", "ArrowUp"):
        page.keyboard.press(key, delay=HELD)
    page.wait_for_timeout(100)
    assert focused(page) == "plain-a"
    wait_for_text(page, "seen", '["b","d","a","d","b","d","a"]')


@CONTRACT.step("vertical tabs move with the up and down arrow keys alone")
def _vertical(run: Run) -> None:
    page = run.page
    page.locator("#upright-a").focus()
    _press(run, "ArrowDown", "upright-b")
    _wait_for_shown(run, "upright", "b")
    _press(run, "ArrowUp", "upright-a")
    _press(run, "ArrowUp", "upright-c")
    _wait_for_shown(run, "upright", "c")
    for key in ("ArrowLeft", "ArrowRight"):
        page.keyboard.press(key, delay=HELD)
    page.wait_for_timeout(100)
    assert focused(page) == "upright-c"


@CONTRACT.step("the left and right arrow keys change places from right to left")
def _rtl(run: Run) -> None:
    page = run.page
    page.locator("#rtl-a").focus()
    _press(run, "ArrowLeft", "rtl-b")
    _wait_for_shown(run, "rtl", "b")
    _press(run, "ArrowRight", "rtl-a")
    _press(run, "ArrowRight", "rtl-c")
    _wait_for_shown(run, "rtl", "c")


@CONTRACT.step("a list that does not loop stops at its ends")
def _ends(run: Run) -> None:
    page = run.page
    page.locator("#ends-a").focus()
    page.keyboard.press("ArrowLeft", delay=HELD)
    page.wait_for_timeout(100)
    assert focused(page) == "ends-a"
    _press(run, "End", "ends-c")
    page.keyboard.press("ArrowRight", delay=HELD)
    page.wait_for_timeout(100)
    assert focused(page) == "ends-c"
    _wait_for_shown(run, "ends", "c")


@CONTRACT.step("tabs activated by hand wait for Enter, Space or a click")
def _manual(run: Run) -> None:
    page = run.page
    page.locator("#manual-a").focus()
    _press(run, "ArrowRight", "manual-b")
    page.wait_for_timeout(100)
    _wait_for_shown(run, "manual", "a")
    page.keyboard.press("Enter")
    _wait_for_shown(run, "manual", "b")
    _press(run, "ArrowRight", "manual-c")
    page.keyboard.press("Space")
    _wait_for_shown(run, "manual", "c")
    page.locator("#manual-a").click()
    _wait_for_shown(run, "manual", "a")


@CONTRACT.step("a click selects a tab and says so once, and not a disabled one")
def _click(run: Run) -> None:
    page = run.page
    page.locator("#plain-b").click()
    _wait_for_shown(run, "plain", "b")
    page.locator("#plain-b").click()
    page.locator("#plain-c").click(force=True)
    page.locator("#plain-d").click()
    _wait_for_shown(run, "plain", "d")
    wait_for_text(page, "seen", '["b","d"]')


@CONTRACT.step("tabs bound to state show the tab of the state")
def _bound(run: Run) -> None:
    page = run.page
    _wait_for_shown(run, "bound", "b")
    page.locator("#bound-a").click()
    wait_for_text(page, "bound-value", "a")
    _wait_for_shown(run, "bound", "a")
    page.locator("#last").click()
    wait_for_text(page, "bound-value", "c")
    _wait_for_shown(run, "bound", "c")
    page.locator("#bound-c").focus()
    _press(run, "ArrowLeft", "bound-b")
    wait_for_text(page, "bound-value", "b")
    _wait_for_shown(run, "bound", "b")


@CONTRACT.step("tabs without a value show no panel until a tab is selected")
def _none(run: Run) -> None:
    page = run.page
    _wait_for_shown(run, "none", "")
    page.locator("#bound-panel-b").focus()
    page.keyboard.press("Tab")
    page.wait_for_function("document.activeElement.id === 'none-a'")
    page.locator("#none-b").click()
    _wait_for_shown(run, "none", "b")
