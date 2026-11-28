"""The select: every variant, size and state of its trigger, and its open list."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from playwright.sync_api import Locator, Page

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.look import Point, State
from ui_parity.matrix import DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import ACCENTS, wait_for_text

VARIANTS = ["surface", "classic", "soft", "ghost"]
SIZES = ["1", "2", "3"]
RADII = ["none", "small", "full"]
OPEN = "open"

# The props of the cell that are the ones of the trigger, and of the list.
_TRIGGER = ("variant", "radius", "placeholder", "width")
_CONTENT = ("high_contrast", "side", "align", "side_offset")


def _select(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a select with two groups of options.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell: of the root, and the ones named above
            of the trigger and of the list. ``look`` is the variant of the
            list, and ``long`` asks for more options than the list has room
            for.

    Returns:
        The select: the list beside its trigger, as rx.ui places it.
    """
    props = dict(props)
    select = namespace.select
    trigger = {key: props.pop(key) for key in _TRIGGER if key in props}
    content = {key: props.pop(key) for key in _CONTENT if key in props}
    if "look" in props:
        content["variant"] = props.pop("look")
    if "color_scheme" in props:
        trigger["color_scheme"] = content["color_scheme"] = props.pop("color_scheme")
    more = [
        select.item(f"Option {number}", value=f"option-{number}")
        for number in range(1, 30 if props.pop("long", False) else 1)
    ]
    if "align" in content:
        # A list that ends at the end of its trigger, or is centered on it,
        # reaches before it: the trigger leaves it room, in both systems.
        return rx.el.div(
            _root(select, trigger, content, props, more, name="A potato"),
            style={"padding_left": "70px"},
        )
    return _root(select, trigger, content, props, more)


def _root(
    select: Any,
    trigger: dict[str, Any],
    content: dict[str, Any],
    props: dict[str, Any],
    more: list[Any],
    name: str = "A potato with a long name",
) -> Any:
    """Create the select of a cell.

    Args:
        select: The namespace of the select.
        trigger: The props of the trigger.
        content: The props of the list.
        props: The props of the root.
        more: Further options.
        name: What the option with the longest name shows.

    Returns:
        The select.
    """
    return select.root(
        select.trigger(**trigger),
        select.content(
            select.group(
                select.label("Fruits"),
                select.item("Apple", value="apple"),
                select.item("Orange", value="orange"),
                select.item("Grape", value="grape", disabled=True),
            ),
            select.separator(),
            select.group(
                select.label("Vegetables"),
                select.item("Carrot", value="carrot"),
                select.item(name, value="potato"),
                *more,
            ),
            position="popper",
            **content,
        ),
        **props,
    )


def _open(page: Page, target: Locator, point: Point) -> None:
    """Open a select with the keyboard, and wait for its list.

    Args:
        page: The page.
        target: The trigger.
        point: The middle of the trigger.
    """
    target.focus()
    page.keyboard.press("Enter")
    page.locator("[role=listbox]:visible [role=option]").first.wait_for()
    page.wait_for_function("document.activeElement.getAttribute('role') === 'option'")


def _close(page: Page, target: Locator, point: Point) -> None:
    """Close the list of a select, and take the focus off its trigger.

    Args:
        page: The page.
        target: The trigger.
        point: The middle of the trigger.
    """
    page.keyboard.press("Escape")
    page.locator("[role=listbox]:visible").wait_for(state="detached")
    page.evaluate("document.activeElement.blur()")


MATRIX = Matrix(
    component="select",
    render=_select,
    base={"default_value": "apple"},
    cross={"variant": VARIANTS, "size": SIZES},
    sweep={
        "color_scheme": ACCENTS,
        "radius": RADII,
        "disabled": [True],
        "default_value": {"none": None, "long": "potato"},
        "placeholder": ["Pick one"],
        "width": ["90px"],
        "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
        "appearance": [DARK],
        "state": [HOVER, FOCUS_VISIBLE, OPEN],
        "viewport": [520],
    },
    groups=[
        {
            "variant": VARIANTS,
            "default_value": {"none": None},
            "placeholder": ["Pick one"],
            "appearance": [LIGHT, DARK],
        },
        {"variant": VARIANTS, "disabled": [True], "appearance": [LIGHT, DARK]},
        {
            "variant": VARIANTS,
            "state": [HOVER, FOCUS_VISIBLE, OPEN],
            "appearance": [LIGHT, DARK],
        },
        {"variant": VARIANTS, "color_scheme": ["ruby", "gray", "yellow"]},
        {"radius": RADII, "size": SIZES, "variant": VARIANTS},
        {
            "look": ["solid", "soft"],
            "high_contrast": [False, True],
            "size": SIZES,
            "state": [OPEN],
            "appearance": [LIGHT, DARK],
        },
        {
            "look": ["solid", "soft"],
            "color_scheme": ["ruby", "gray", "yellow"],
            "high_contrast": [False, True],
            "state": [OPEN],
        },
        {"default_value": {"none": None, "long": "potato"}, "state": [OPEN]},
        {
            "align": ["start", "center", "end"],
            "width": ["90px", "220px"],
            "state": [OPEN],
        },
        {"side_offset": [0, 12], "state": [OPEN]},
        {"long": [True], "size": SIZES, "state": [OPEN]},
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
            "viewport": [520, 800, 1100],
        },
    ],
    stage=(280, 330),
    crop="stage",
    target="button",
    parts={"shown": "button > span", "icon": "button > svg"},
    states={
        OPEN: State(enter=_open, leave=_close, matches="[data-state='open']"),
    },
    # The trigger of Radix shows nothing until JavaScript has found the text
    # of the chosen option, some time after the page is hydrated.
    ready=(
        "[...document.querySelectorAll('[role=combobox]')].every("
        "trigger => trigger.hasAttribute('data-placeholder')"
        " || trigger.textContent !== '')"
    ),
    # Not held to zero. At a threshold of zero most cells are equal pixel
    # for pixel, and the others differ by where they are on the page: the
    # gradients of the classic trigger are dithered by a step of a channel,
    # as the trigger of Radix is against itself at another place. At the
    # default threshold 2 cells differ, by at most 2 pixels of 92400, on the
    # icon of a trigger whose long text puts it on a fraction of a pixel.
    tolerance=0.0001,
)


class SelectState(rx.State):
    """What the selects of the contract are bound to."""

    bound: rx.Field[str] = rx.field("banana")
    seen: rx.Field[list[str]] = rx.field(default_factory=list)
    opened: rx.Field[list[bool]] = rx.field(default_factory=list)
    clicks: rx.Field[int] = rx.field(0)
    submitted: rx.Field[dict[str, str]] = rx.field(default_factory=dict)
    submissions: rx.Field[int] = rx.field(0)

    @rx.event
    def set_bound(self, value: str):
        """Follow the bound select.

        Args:
            value: The value it chose.
        """
        self.bound = value

    @rx.event
    def see(self, value: str):
        """Keep what a change handed over.

        Args:
            value: The chosen value.
        """
        self.seen.append(value)

    @rx.event
    def see_open(self, value: bool):
        """Keep whether a list opened or closed.

        Args:
            value: Whether it is open.
        """
        self.opened.append(value)

    @rx.event
    def pick_cherry(self):
        """Change the bound value from outside the select."""
        self.bound = "cherry"

    @rx.event
    def click(self):
        """Count a click on the button beside the selects."""
        self.clicks += 1

    @rx.event
    def submit(self, data: dict[str, str]):
        """Keep what a form submitted.

        Args:
            data: The values of the form.
        """
        self.submitted = data
        self.submissions += 1


def _fruits(namespace: Any, trigger: str, **props: Any) -> Any:
    """Create a select of fruits.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        trigger: The id of its trigger.
        **props: The props of its root.

    Returns:
        The select: one of its options is disabled, and one is outside the
        group the others are in.
    """
    select = namespace.select
    return select.root(
        select.trigger(placeholder="Pick a fruit", id=trigger),
        select.content(
            select.group(
                select.label("Fruits"),
                select.item("Apple", value="apple"),
                select.item("Apricot", value="apricot"),
                select.item("Banana", value="banana"),
                select.item("Blueberry", value="blueberry", disabled=True),
                select.item("Cherry", value="cherry"),
            ),
            select.separator(),
            select.item("Nothing at all", value="none"),
            position="popper",
        ),
        **props,
    )


CONTRACT = Contract(
    component="select",
    render=lambda namespace: namespace.box(
        _fruits(
            namespace,
            "pick",
            on_change=SelectState.see,
            on_open_change=SelectState.see_open,
        ),
        _fruits(namespace, "chosen", default_value="apricot"),
        _fruits(
            namespace,
            "bound",
            value=SelectState.bound,
            on_change=SelectState.set_bound,
        ),
        namespace.select(
            ["Small", "Medium", "Large"], default_value="Medium", id="size"
        ),
        _fruits(namespace, "off", disabled=True),
        rx.el.button("Cherry", id="cherry", on_click=SelectState.pick_cherry),
        rx.el.button("Beside", id="beside", on_click=SelectState.click),
        rx.el.form(
            _fruits(namespace, "wanted", name="wanted", required=True),
            _fruits(namespace, "given", name="given", default_value="cherry"),
            rx.el.button("Send", id="send", type="submit"),
            on_submit=SelectState.submit,
            id="form",
        ),
        rx.el.span(SelectState.seen.to_string(), id="seen"),
        rx.el.span(SelectState.opened.to_string(), id="opened"),
        rx.el.span(SelectState.bound, id="bound-value"),
        rx.el.span(SelectState.clicks.to_string(), id="clicks"),
        rx.el.span(SelectState.submitted.to_string(), id="submitted"),
        rx.el.span(SelectState.submissions.to_string(), id="submissions"),
    ),
)

# The list that is open, and its options.
LIST = "[role=listbox]:visible"
# The text of the option that has the focus, or of anything else that has it.
FOCUSED_OPTION = (
    "document.activeElement.getAttribute('role') === 'option'"
    " ? document.activeElement.textContent : document.activeElement.id"
)


def _trigger(run: Run, trigger: str) -> Any:
    """Find the trigger of a select.

    Args:
        run: The run, on a page.
        trigger: Its id.

    Returns:
        The trigger.
    """
    return run.page.locator(f"[id='{trigger}']")


def _open_list(run: Run, trigger: str, key: str = "Enter") -> None:
    """Open a select with the keyboard, and wait for an option to have the focus.

    Args:
        run: The run, on a page.
        trigger: The id of its trigger.
        key: The key that opens it.
    """
    page = run.page
    _trigger(run, trigger).focus()
    page.keyboard.press(key)
    page.locator(LIST).wait_for()
    page.wait_for_function("document.activeElement.getAttribute('role') === 'option'")


def _wait_for_closed(run: Run) -> None:
    """Wait until no list is open.

    Args:
        run: The run, on a page.
    """
    run.page.locator(LIST).wait_for(state="detached")


def _wait_for_focus(run: Run, text: str) -> None:
    """Wait until an option, or another element, has the focus.

    Args:
        run: The run, on a page.
        text: The text of the option, or the id of the element.
    """
    run.page.wait_for_function(f"text => ({FOCUSED_OPTION}) === text", arg=text)


def _wait_for_shown(run: Run, trigger: str, text: str) -> None:
    """Wait until the trigger of a select shows a text.

    Args:
        run: The run, on a page.
        trigger: The id of the trigger.
        text: Its whole text.
    """
    wait_for_text(run.page, trigger, text)


@CONTRACT.step("its trigger is a button in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    pick = run.server.element("pick")
    assert (pick.tag, pick.attributes["role"], pick.attributes["type"]) == (
        "button",
        "combobox",
        "button",
    )
    assert pick.text == "Pick a fruit"


@CONTRACT.step("shows the chosen option in the server render", on=SERVER)
def _server_value(run: Run) -> None:
    assert run.server.element("chosen").text == "Apricot"
    assert run.server.element("size").text == "Medium"
    assert run.server.element("bound").text == "Banana"


@CONTRACT.step("opens and closes its list with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    page = run.page
    page.set_default_timeout(3000)
    _trigger(run, "chosen").click()
    page.locator(LIST).wait_for()
    assert page.locator(LIST).get_by_role("option").all_text_contents() == [
        "Apple",
        "Apricot",
        "Banana",
        "Blueberry",
        "Cherry",
        "Nothing at all",
    ]
    page.keyboard.press("Escape")
    _wait_for_closed(run)


@CONTRACT.step("has the roles, the names and the states of a select")
def _role(run: Run) -> None:
    page = run.page
    assert page.get_by_role("combobox").count() == 7
    chosen = _trigger(run, "chosen")
    assert chosen.get_attribute("aria-expanded") == "false"
    assert page.get_by_role("combobox", disabled=True).count() == 1
    _open_list(run, "chosen")
    assert chosen.get_attribute("aria-expanded") == "true"
    assert chosen.get_attribute("aria-controls") == page.locator(LIST).get_attribute(
        "id"
    )
    options = page.get_by_role("listbox")
    assert options.get_by_role("option", selected=True).all_text_contents() == [
        "Apricot"
    ]
    assert options.get_by_role("option", disabled=True).all_text_contents() == [
        "Blueberry"
    ]
    assert (
        options.get_by_role("group", name="Fruits").get_by_role("option").count() == 5
    )


@CONTRACT.step("Enter, Space and the arrow keys open the list, on the chosen option")
def _open_keys(run: Run) -> None:
    page = run.page
    for key in ("Enter", "Space", "ArrowDown", "ArrowUp"):
        _open_list(run, "chosen", key)
        _wait_for_focus(run, "Apricot")
        page.keyboard.press("Escape")
        _wait_for_closed(run)
        _wait_for_focus(run, "chosen")
    _open_list(run, "pick")
    _wait_for_focus(run, "Apple")


@CONTRACT.step(
    "the arrow keys, Home and End move through the options that can be chosen"
)
def _move(run: Run) -> None:
    page = run.page
    _open_list(run, "chosen")
    for key, option in (
        ("ArrowDown", "Banana"),
        ("ArrowDown", "Cherry"),
        ("ArrowDown", "Nothing at all"),
        ("ArrowDown", "Nothing at all"),
        ("ArrowUp", "Cherry"),
        ("Home", "Apple"),
        ("ArrowUp", "Apple"),
        ("End", "Nothing at all"),
    ):
        page.keyboard.press(key)
        _wait_for_focus(run, option)
    assert _trigger(run, "chosen").text_content() == "Apricot"


@CONTRACT.step(
    "Enter chooses the option that has the focus, and the trigger has it back"
)
def _choose(run: Run) -> None:
    page = run.page
    _open_list(run, "pick")
    page.keyboard.press("ArrowDown")
    _wait_for_focus(run, "Apricot")
    page.keyboard.press("Enter")
    _wait_for_closed(run)
    _wait_for_shown(run, "pick", "Apricot")
    _wait_for_focus(run, "pick")
    wait_for_text(page, "seen", '["apricot"]')
    _open_list(run, "pick")
    _wait_for_focus(run, "Apricot")
    assert page.get_by_role("listbox").get_by_role(
        "option", selected=True
    ).all_text_contents() == ["Apricot"]
    page.keyboard.press("End")
    _wait_for_focus(run, "Nothing at all")
    page.keyboard.press("Space")
    _wait_for_closed(run)
    _wait_for_shown(run, "pick", "Nothing at all")
    wait_for_text(page, "seen", '["apricot","none"]')


@CONTRACT.step("a click chooses an option, and not a disabled one")
def _click(run: Run) -> None:
    page = run.page
    _trigger(run, "pick").click()
    page.locator(LIST).wait_for()
    page.locator(LIST).get_by_role("option", name="Blueberry").click(force=True)
    assert page.locator(LIST).is_visible()
    page.locator(LIST).get_by_role("option", name="Cherry").click()
    _wait_for_closed(run)
    _wait_for_shown(run, "pick", "Cherry")
    wait_for_text(page, "seen", '["cherry"]')


@CONTRACT.step("Escape closes the list and chooses nothing")
def _escape(run: Run) -> None:
    page = run.page
    _open_list(run, "chosen")
    page.keyboard.press("ArrowDown")
    _wait_for_focus(run, "Banana")
    page.keyboard.press("Escape")
    _wait_for_closed(run)
    _wait_for_focus(run, "chosen")
    assert _trigger(run, "chosen").text_content() == "Apricot"
    assert _trigger(run, "chosen").get_attribute("aria-expanded") == "false"


@CONTRACT.step("Tab stays in an open list")
def _tab(run: Run) -> None:
    page = run.page
    _open_list(run, "chosen")
    page.keyboard.press("Tab")
    assert page.locator(LIST).is_visible()
    assert page.evaluate(FOCUSED_OPTION) == "Apricot"


@CONTRACT.step("typing goes to the option that starts with what is typed")
def _type(run: Run) -> None:
    page = run.page
    _open_list(run, "pick")
    page.keyboard.type("ch")
    _wait_for_focus(run, "Cherry")
    page.keyboard.press("Escape")
    _wait_for_closed(run)
    page.wait_for_timeout(1100)
    _trigger(run, "pick").focus()
    page.keyboard.type("b")
    _wait_for_shown(run, "pick", "Banana")
    assert not page.locator(LIST).is_visible()
    wait_for_text(page, "seen", '["banana"]')


@CONTRACT.step("says when its list opens and closes")
def _open_change(run: Run) -> None:
    page = run.page
    _open_list(run, "pick")
    wait_for_text(page, "opened", "[true]")
    page.keyboard.press("Escape")
    wait_for_text(page, "opened", "[true,false]")


@CONTRACT.step("a pointer outside the list closes it")
def _outside(run: Run) -> None:
    page = run.page
    _open_list(run, "chosen")
    page.mouse.click(1000, 600)
    _wait_for_closed(run)
    assert _trigger(run, "chosen").text_content() == "Apricot"


@CONTRACT.step("the page behind an open list takes no click")
def _modal(run: Run) -> None:
    page = run.page
    _open_list(run, "chosen")
    box = page.locator("#beside").bounding_box()
    assert box is not None
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    _wait_for_closed(run)
    page.wait_for_timeout(300)
    assert page.locator("#clicks").text_content() == "0"


@CONTRACT.step("a disabled select does not open")
def _disabled(run: Run) -> None:
    page = run.page
    _trigger(run, "off").click(force=True)
    page.wait_for_timeout(200)
    assert page.locator(LIST).count() == 0
    assert _trigger(run, "off").is_disabled()


@CONTRACT.step("a select bound to state shows the value of the state")
def _bound(run: Run) -> None:
    page = run.page
    _wait_for_shown(run, "bound", "Banana")
    page.locator("#cherry").click()
    _wait_for_shown(run, "bound", "Cherry")
    _open_list(run, "bound")
    _wait_for_focus(run, "Cherry")
    page.keyboard.press("Home")
    _wait_for_focus(run, "Apple")
    page.keyboard.press("Enter")
    wait_for_text(page, "bound-value", "apple")
    _wait_for_shown(run, "bound", "Apple")


@CONTRACT.step("the select of a list of words shows and chooses them")
def _words(run: Run) -> None:
    page = run.page
    _wait_for_shown(run, "size", "Medium")
    _open_list(run, "size")
    assert page.locator(LIST).get_by_role("option").all_text_contents() == [
        "Small",
        "Medium",
        "Large",
    ]
    _wait_for_focus(run, "Medium")
    page.keyboard.press("ArrowDown")
    _wait_for_focus(run, "Large")
    page.keyboard.press("Enter")
    _wait_for_shown(run, "size", "Large")


@CONTRACT.step("a form waits for a required select, then submits each by its name")
def _form(run: Run) -> None:
    page = run.page
    page.locator("#send").click()
    page.wait_for_timeout(300)
    assert page.locator("#submissions").text_content() == "0"
    _open_list(run, "wanted")
    _wait_for_focus(run, "Apple")
    page.keyboard.press("Enter")
    _wait_for_shown(run, "wanted", "Apple")
    page.locator("#send").click()
    wait_for_text(page, "submissions", "1")
    assert page.locator("#submitted").text_content() == (
        '{"wanted":"apple","given":"cherry"}'
    )
