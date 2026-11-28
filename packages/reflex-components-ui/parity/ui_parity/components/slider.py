"""The slider: every variant, size and state, and what moves its thumbs."""

from __future__ import annotations

from typing import Any

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.look import FOCUS_WITHIN
from ui_parity.matrix import DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix
from ui_parity.samples import ACCENTS, focused, wait_for_text

VARIANTS = ["classic", "surface", "soft"]
SIZES = ["1", "2", "3"]
RADII = ["none", "small", "full"]
VALUES = {"start": [0], "end": [100], "two": [20, 60], "three": [10, 50, 90]}

MATRIX = Matrix(
    component="slider",
    base={"default_value": [40]},
    cross={"variant": VARIANTS, "size": SIZES},
    sweep={
        "color_scheme": ACCENTS,
        "radius": RADII,
        "high_contrast": [True],
        "disabled": [True],
        "default_value": VALUES,
        "width": ["120px"],
        "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
        "appearance": [DARK],
        "state": [HOVER, FOCUS_VISIBLE],
        "viewport": [520],
    },
    groups=[
        {
            "variant": VARIANTS,
            "high_contrast": [False, True],
            "appearance": [LIGHT, DARK],
            "default_value": {"two": [20, 60]},
        },
        {
            "variant": VARIANTS,
            "disabled": [True],
            "appearance": [LIGHT, DARK],
            "default_value": {"one": [40], "two": [20, 60]},
        },
        {"variant": VARIANTS, "state": [FOCUS_VISIBLE], "appearance": [LIGHT, DARK]},
        {
            "variant": VARIANTS,
            "color_scheme": ["ruby", "gray", "yellow"],
            "high_contrast": [False, True],
        },
        {"radius": RADII, "size": SIZES, "variant": VARIANTS},
        {"default_value": VALUES, "size": SIZES},
        {
            "orientation": ["vertical"],
            "height": ["100px"],
            "default_value": {"one": [40], "two": [20, 60]},
            "variant": VARIANTS,
        },
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
            "viewport": [520, 800, 1100],
        },
    ],
    stage=(240, 140),
    crop="stage",
    parts={
        "track": "span > span",
        "range": "span > span > span",
    },
    # The focus is on the first thumb: an element of Radix, an input here.
    states={FOCUS_VISIBLE: FOCUS_WITHIN},
    # Not held to zero. At a threshold of zero 102 of the 147 cells are
    # equal pixel for pixel, and the others differ by where they are on the
    # page: the translucent layers of the soft track are dithered by a step
    # of a channel, and the round thumb is anti-aliased otherwise. At the
    # default threshold 5 cells differ, by at most 2 pixels of 33600.
    tolerance=0.0001,
)


class SliderState(rx.State):
    """What the sliders of the contract are bound to."""

    bound: list[int] = [10]
    seen: list[list[float]] = []
    committed: list[list[float]] = []
    submitted: dict[str, Any] = {}
    submissions: int = 0

    @rx.event
    def set_bound(self, values: list[float]):
        """Follow the bound slider.

        Args:
            values: Its values.
        """
        self.bound = [int(value) for value in values]

    @rx.event
    def see(self, values: list[float]):
        """Keep what a change handed over.

        Args:
            values: The values of the slider.
        """
        self.seen.append(values)

    @rx.event
    def commit(self, values: list[float]):
        """Keep what a released thumb handed over.

        Args:
            values: The values of the slider.
        """
        self.committed.append(values)

    @rx.event
    def set_high(self):
        """Change the bound value from outside the slider."""
        self.bound = [80]

    @rx.event
    def submit(self, data: dict[str, Any]):
        """Keep what a form submitted.

        Args:
            data: The values of the form.
        """
        self.submitted = data
        self.submissions += 1


WIDTH = {"width": "200px", "padding": "12px 0"}

CONTRACT = Contract(
    component="slider",
    render=lambda namespace: namespace.box(
        rx.el.div(
            namespace.slider(
                default_value=30,
                aria_label="Volume",
                on_change=SliderState.see,
                on_value_commit=SliderState.commit,
            ),
            id="volume",
            style=WIDTH,
        ),
        rx.el.div(
            namespace.slider(default_value=30, disabled=True, aria_label="Off"),
            id="off",
            style=WIDTH,
        ),
        rx.el.div(
            namespace.slider(
                value=SliderState.bound,
                on_change=SliderState.set_bound,
                aria_label="Bound",
            ),
            id="bound",
            style=WIDTH,
        ),
        rx.el.button("High", id="high", on_click=SliderState.set_high),
        rx.el.div(
            namespace.slider(
                default_value=[20, 60], aria_label="Span", on_change=SliderState.see
            ),
            id="span",
            style=WIDTH,
        ),
        rx.el.div(
            namespace.slider(
                default_value=4, min=0, max=10, step=2, aria_label="Steps"
            ),
            id="steps",
            style=WIDTH,
        ),
        rx.el.form(
            namespace.slider(default_value=25, name="level", aria_label="Level"),
            rx.el.button("Send", id="send", type="submit"),
            on_submit=SliderState.submit,
            id="form",
            style=WIDTH,
        ),
        rx.el.span(SliderState.seen.to_string(), id="seen"),
        rx.el.span(SliderState.committed.to_string(), id="committed"),
        rx.el.span(SliderState.bound.to_string(), id="bound-value"),
        rx.el.span(SliderState.submitted.to_string(), id="submitted"),
        rx.el.span(SliderState.submissions.to_string(), id="submissions"),
    ),
)

# A thumb is an element with the role of a slider in Radix, a range input here.
THUMBS = "[role=slider], input[type=range]"
# The values of the thumbs of a slider, by the id of its frame.
VALUES_OF = (
    f"id => [...document.getElementById(id).querySelectorAll('{THUMBS}')]"
    ".map(thumb => Number(thumb.getAttribute('aria-valuenow') ?? thumb.value))"
)
# The slider whose thumb has the focus, and which of its thumbs it is.
FOCUSED_THUMB = (
    "(thumb => thumb.closest('div[id]')?.id + ':' + "
    f"[...thumb.closest('div[id]')?.querySelectorAll('{THUMBS}') ?? []].indexOf(thumb))"
    "(document.activeElement)"
)


def _wait_for_values(run: Run, slider: str, values: list[float]) -> None:
    """Wait until the thumbs of a slider have the values expected.

    Args:
        run: The run, on a page.
        slider: The id of the frame of the slider.
        values: The value of each thumb.
    """
    run.page.wait_for_function(
        f"([id, values]) => ({VALUES_OF})(id).join() === values",
        arg=[slider, ",".join(str(value) for value in values)],
    )


def _thumb(run: Run, slider: str, index: int = 0) -> Any:
    """Find a thumb of a slider.

    Args:
        run: The run, on a page.
        slider: The id of the frame of the slider.
        index: Which of its thumbs.

    Returns:
        The thumb.
    """
    return run.page.locator(f"#{slider}").locator(THUMBS).nth(index)


@CONTRACT.step("is in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    assert run.server.element("volume").tag == "div"
    assert run.server.element("form").tag == "form"


@CONTRACT.step("moves with the keyboard with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    page = run.page
    page.set_default_timeout(3000)
    _wait_for_values(run, "volume", [30])
    page.keyboard.press("Tab")
    page.keyboard.press("ArrowRight")
    _wait_for_values(run, "volume", [31])


@CONTRACT.step("each thumb is a slider with its value and its range")
def _role(run: Run) -> None:
    page = run.page
    volume = page.locator("#volume").get_by_role("slider")
    assert volume.count() == 1
    assert volume.evaluate(
        "thumb => ['min', 'max', 'now'].map(name =>"
        " thumb.getAttribute('aria-value' + name)"
        " ?? (name === 'now' ? thumb.value : thumb[name] || (name === 'min' ? '0' : '100')))"
    ) == ["0", "100", "30"]
    assert page.locator("#span").get_by_role("slider").count() == 2
    assert page.locator("#off").get_by_role("slider", disabled=True).count() == 1
    assert page.evaluate(VALUES_OF, "span") == [20, 60]
    span = page.locator("#span")
    assert span.get_by_role("slider", name="Minimum").count() == 1
    assert span.get_by_role("slider", name="Maximum").count() == 1


@CONTRACT.step("the thumb of a slider has the name the slider is given")
def _name(run: Run) -> None:
    page = run.page
    page.set_default_timeout(3000)
    assert page.get_by_role("slider", name="Volume").count() == 1
    assert page.get_by_role("slider", name="Off", disabled=True).count() == 1


@CONTRACT.step("Tab stops on each thumb but a disabled one")
def _tab(run: Run) -> None:
    page = run.page
    stops = []
    for _ in range(6):
        page.keyboard.press("Tab")
        stops.append(focused(page) or page.evaluate(FOCUSED_THUMB))
    assert stops == ["volume:0", "bound:0", "high", "span:0", "span:1", "steps:0"]


@CONTRACT.step("the arrow keys, the page keys, Home and End move a thumb, and say so")
def _keys(run: Run) -> None:
    page = run.page
    _thumb(run, "volume").focus()
    for key, value in (
        ("ArrowRight", 31),
        ("ArrowUp", 32),
        ("ArrowLeft", 31),
        ("ArrowDown", 30),
        ("PageUp", 40),
        ("PageDown", 30),
        ("End", 100),
        ("Home", 0),
    ):
        page.keyboard.press(key)
        _wait_for_values(run, "volume", [value])
    values = "[[31],[32],[31],[30],[40],[30],[100],[0]]"
    wait_for_text(page, "seen", values)
    wait_for_text(page, "committed", values)


@CONTRACT.step("Shift and an arrow key move a thumb by ten steps")
def _shift(run: Run) -> None:
    page = run.page
    page.set_default_timeout(3000)
    _thumb(run, "volume").focus()
    page.keyboard.press("Shift+ArrowRight")
    _wait_for_values(run, "volume", [40])


@CONTRACT.step("a thumb moves by the step of its slider, within its range")
def _steps(run: Run) -> None:
    page = run.page
    _thumb(run, "steps").focus()
    page.keyboard.press("ArrowRight")
    _wait_for_values(run, "steps", [6])
    page.keyboard.press("End")
    page.keyboard.press("ArrowRight")
    _wait_for_values(run, "steps", [10])


@CONTRACT.step("a pointer on the track moves the thumb there, and releasing it says so")
def _pointer(run: Run) -> None:
    page = run.page
    box = page.locator("#volume").bounding_box()
    assert box is not None
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    _wait_for_values(run, "volume", [50])
    wait_for_text(page, "seen", "[[50]]")
    wait_for_text(page, "committed", "[[50]]")


@CONTRACT.step("a disabled slider does not move")
def _disabled(run: Run) -> None:
    page = run.page
    box = page.locator("#off").bounding_box()
    assert box is not None
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.keyboard.press("ArrowRight")
    _thumb(run, "volume").focus()
    page.keyboard.press("ArrowRight")
    _wait_for_values(run, "volume", [31])
    assert page.evaluate(VALUES_OF, "off") == [30]


@CONTRACT.step("follows the state it is bound to")
def _bound(run: Run) -> None:
    page = run.page
    _wait_for_values(run, "bound", [10])
    _thumb(run, "bound").focus()
    page.keyboard.press("ArrowRight")
    wait_for_text(page, "bound-value", "[11]")
    _wait_for_values(run, "bound", [11])
    page.locator("#high").click()
    wait_for_text(page, "bound-value", "[80]")
    _wait_for_values(run, "bound", [80])


@CONTRACT.step("a slider with two values has a thumb for each, and hands over both")
def _two(run: Run) -> None:
    page = run.page
    _thumb(run, "span", 0).focus()
    page.keyboard.press("ArrowRight")
    _wait_for_values(run, "span", [21, 60])
    _thumb(run, "span", 1).focus()
    page.keyboard.press("ArrowLeft")
    _wait_for_values(run, "span", [21, 59])
    wait_for_text(page, "seen", "[[21,60],[21,59]]")


@CONTRACT.step("a pointer on the track of a slider with two thumbs moves the nearest")
def _nearest(run: Run) -> None:
    page = run.page
    box = page.locator("#span").bounding_box()
    assert box is not None
    page.mouse.click(box["x"] + box["width"] * 0.75, box["y"] + box["height"] / 2)
    _wait_for_values(run, "span", [20, 75])
    page.wait_for_function(f"{FOCUSED_THUMB} === 'span:1'")
    wait_for_text(page, "seen", "[[20,75]]")


@CONTRACT.step("a thumb can be moved past the one after it")
def _past(run: Run) -> None:
    page = run.page
    page.set_default_timeout(3000)
    _thumb(run, "span", 0).focus()
    for _ in range(5):
        page.keyboard.press("PageUp")
    _wait_for_values(run, "span", [60, 70])


@CONTRACT.step("submits its value with a form")
def _submit(run: Run) -> None:
    page = run.page
    _thumb(run, "form").focus()
    page.keyboard.press("ArrowRight")
    page.locator("#send").click()
    wait_for_text(page, "submissions", "1")
    assert page.locator("#submitted").text_content() == '{"level":"26"}'
