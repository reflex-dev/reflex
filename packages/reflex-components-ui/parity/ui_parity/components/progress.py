"""The progress bar: every value, variant and size, and a bar without a value."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, LIGHT, Matrix
from ui_parity.samples import ACCENTS

VARIANTS = ["classic", "surface", "soft"]
SIZES = ["1", "2", "3"]
RADII = ["none", "small", "medium", "large", "full"]

# A bar without a value: the prop is left out.
INDETERMINATE = {"indeterminate": None}

INDICATOR = "[role='progressbar'] > div"


def _progress(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a progress bar, without the value of a cell that has none.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell.

    Returns:
        The progress bar.
    """
    return namespace.progress(**{
        name: value for name, value in props.items() if value is not None
    })


MATRIX = Matrix(
    component="progress",
    render=_progress,
    base={"value": 40},
    cross={"variant": VARIANTS, "size": SIZES},
    sweep={
        # Whole and fractional widths, the ends, and a value over the
        # maximum, which is no value: the bar is indeterminate.
        "value": {
            **INDETERMINATE,
            **{str(value): value for value in (0, 1, 25, 33, 50, 75, 99, 100, 150)},
        },
        "max": [40, 60, 250],
        "color_scheme": ACCENTS,
        "high_contrast": [True],
        "radius": RADII,
        "fill_color": ["crimson"],
        "duration": ["2s"],
        "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        {
            "variant": VARIANTS,
            "high_contrast": [False, True],
            "appearance": [LIGHT, DARK],
        },
        # The frame an indeterminate bar is frozen on: grown to the whole
        # track, under its shine.
        {
            "value": INDETERMINATE,
            "variant": VARIANTS,
            "high_contrast": [False, True],
            "appearance": [LIGHT, DARK],
        },
        {"value": INDETERMINATE, "size": SIZES, "radius": ["none", "full"]},
        {"value": INDETERMINATE, "duration": ["2s"], "fill_color": ["crimson"]},
        {
            "variant": VARIANTS,
            "color_scheme": ["ruby", "gray", "yellow"],
            "high_contrast": [False, True],
        },
        {
            "variant": VARIANTS,
            "fill_color": ["crimson"],
            "high_contrast": [False, True],
        },
        {"size": SIZES, "radius": RADII},
        {"value": [3, 97], "radius": ["full"], "size": SIZES},
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="3", lg="2")},
            "viewport": [520, 800, 1100, 1280],
        },
    ],
    stage=(200, 48),
    parts={"indicator": INDICATOR},
    # The threshold is not held to zero, the tolerance is. At a threshold of
    # zero 127 of the 139 cells are equal pixel for pixel. In the others one
    # channel is off by one step, by where the frame is on the page: the
    # translucent layers of a track (the ring of its shadow over its gray,
    # the gradient the soft variant blends in) are rounded one way or the
    # other, the same props being equal in another frame and at another
    # viewport.
    tolerance=0,
)


class ProgressState(rx.State):
    """How far the bar of the contract is."""

    done: rx.Field[int] = rx.field(20)

    @rx.event
    def advance(self):
        """Move the bar on."""
        self.done = 80


CONTRACT = Contract(
    component="progress",
    render=lambda namespace: namespace.box(
        namespace.progress(value=30, id="some"),
        namespace.progress(value=5, max=5, id="all"),
        namespace.progress(id="waiting"),
        namespace.progress(value=ProgressState.done, id="bound"),
        rx.el.button("Advance", id="advance", on_click=ProgressState.advance),
        width="300px",
    ),
)

# What an indeterminate bar plays, as `getAnimations()` reports it: the
# indicator grows, fades and pulses, and a shine crosses it.
ANIMATIONS = """element => element.getAnimations({subtree: true}).map(animation => {
    const {delay, duration, iterations, fill, direction, easing} =
        animation.effect.getTiming();
    return {
        on: animation.effect.pseudoElement,
        timing: {delay, duration, iterations, fill, direction, easing},
        frames: animation.effect.getKeyframes().map(
            ({computedOffset, composite, ...frame}) => frame
        ),
    };
})"""

_GROW = [
    {"offset": 0, "easing": "ease", "transform": "scaleX(0.01)"},
    {"offset": 0.2, "easing": "ease", "transform": "scaleX(0.1)"},
    {"offset": 0.3, "easing": "ease", "transform": "scaleX(0.6)"},
    {"offset": 0.4, "easing": "ease", "transform": "scaleX(0.9)"},
    {"offset": 0.5, "easing": "ease", "transform": "scaleX(0.9)"},
    {"offset": 1, "easing": "ease", "transform": "scaleX(1)"},
]

# The blue of the theme: its track color, and the step it fades to.
_TRACK = "rgb(0, 144, 255)"
_FADED = "rgb(142, 200, 246)"

EXPECTED_ANIMATIONS = [
    {
        "on": None,
        "timing": {
            "delay": 0,
            "duration": 5000,
            "iterations": 1,
            "fill": "both",
            "direction": "normal",
            "easing": "linear",
        },
        "frames": _GROW,
    },
    {
        "on": None,
        "timing": {
            "delay": 10000,
            "duration": 2500,
            "iterations": 1,
            "fill": "none",
            "direction": "normal",
            "easing": "linear",
        },
        "frames": [
            {"offset": 0, "easing": "ease", "backgroundColor": _TRACK},
            {"offset": 1, "easing": "ease", "backgroundColor": _FADED},
        ],
    },
    {
        "on": None,
        "timing": {
            "delay": 12500,
            "duration": 5000,
            "iterations": float("inf"),
            "fill": "none",
            "direction": "alternate",
            "easing": "linear",
        },
        "frames": [
            {"offset": 0, "easing": "ease", "backgroundColor": _FADED},
            {"offset": 1, "easing": "ease", "backgroundColor": _TRACK},
        ],
    },
    {
        "on": "::after",
        "timing": {
            "delay": 10000,
            "duration": 5000,
            "iterations": float("inf"),
            "fill": "backwards",
            "direction": "normal",
            "easing": "linear",
        },
        "frames": [
            {"offset": 0, "easing": "ease", "transform": "translate(-100%)"},
            {"offset": 1, "easing": "ease", "transform": "translate(0%)"},
        ],
    },
]


# How much of its track the indicator of a bar covers, in thousandths.
COVERED = (
    "(element => Math.round(1000"
    " * element.firstElementChild.getBoundingClientRect().width"
    " / element.getBoundingClientRect().width))"
)


def _covered(run: Run, bar: str) -> int:
    """Read how much of its track the indicator of a bar covers.

    Args:
        run: The run, on a page.
        bar: The id of the bar.

    Returns:
        The width of the indicator over the width of the bar, in thousandths.
    """
    return run.page.locator(f"#{bar}").evaluate(COVERED)


@CONTRACT.step("is a progressbar with its value in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    some = run.server.element("some")
    assert some.tag == "div"
    assert {
        name: value
        for name, value in some.attributes.items()
        if name.startswith(("aria-", "data-", "role"))
    } == {
        "aria-valuemax": "100",
        "aria-valuemin": "0",
        "aria-valuenow": "30",
        "aria-valuetext": "30%",
        "role": "progressbar",
        "data-state": "loading",
        "data-value": "30",
        "data-max": "100",
    }
    done = run.server.element("all").attributes
    assert (done["aria-valuenow"], done["aria-valuemax"], done["data-state"]) == (
        "5",
        "5",
        "complete",
    )
    waiting = run.server.element("waiting").attributes
    assert "aria-valuenow" not in waiting
    assert waiting["data-state"] == "indeterminate"
    assert run.server.element("bound").attributes["aria-valuenow"] == "20"


@CONTRACT.step("shows its value with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    assert _covered(run, "some") == 300
    assert _covered(run, "all") == 1000
    assert _covered(run, "bound") == 200
    assert run.page.get_by_role("progressbar").count() == 4


@CONTRACT.step("has the role and the value of a progressbar", on=HYDRATED)
def _role(run: Run) -> None:
    assert run.page.locator("main").aria_snapshot() == (
        "- main:\n"
        "  - progressbar\n"
        "  - progressbar\n"
        "  - progressbar\n"
        "  - progressbar\n"
        '  - button "Advance"'
    )
    names = ("aria-valuemin", "aria-valuenow", "aria-valuemax", "aria-valuetext")
    assert [
        [run.page.locator(f"#{bar}").get_attribute(name) for name in names]
        for bar in ("some", "all", "waiting", "bound")
    ] == [
        ["0", "30", "100", "30%"],
        ["0", "5", "5", "100%"],
        ["0", None, "100", None],
        ["0", "20", "100", "20%"],
    ]


@CONTRACT.step("a bar without a value grows, fades, pulses and shines", on=HYDRATED)
def _animations(run: Run) -> None:
    indicator = run.page.locator("#waiting > div")
    assert indicator.evaluate(ANIMATIONS) == EXPECTED_ANIMATIONS
    assert run.page.locator("#some > div").evaluate(ANIMATIONS) == []


@CONTRACT.step("a value bound to state moves the indicator", on=HYDRATED)
def _bound(run: Run) -> None:
    assert _covered(run, "bound") == 200
    run.page.locator("#advance").click()
    run.page.wait_for_function(
        "document.getElementById('bound').getAttribute('aria-valuenow') === '80'"
    )
    bound = run.page.locator("#bound")
    assert bound.get_attribute("aria-valuetext") == "80%"
    assert bound.get_attribute("data-state") == "loading"
    run.page.wait_for_function(f"{COVERED}(document.getElementById('bound')) === 800")
