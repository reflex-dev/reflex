"""The spinner: its sizes, what it stands in for, and how it turns."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix

RESPONSIVE = rx.breakpoints(initial="1", sm="3", lg="2")


def _spinner(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a spinner, alone, over what it stands in for, or in colored text.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``holds`` names the children, and
            ``inside`` what is around the spinner.

    Returns:
        The spinner, or what is around it.
    """
    props = dict(props)
    holds = props.pop("holds", None)
    inside = props.pop("inside", None)
    children = ["Loading the report"] if holds == "words" else []
    if holds == "box":
        children = [rx.el.div(style={"width": "80px", "height": "40px"})]
    spinner = namespace.spinner(*children, **props)
    if inside == "colored":
        return rx.el.div(spinner, style={"color": "crimson"})
    return spinner


MATRIX = Matrix(
    component="spinner",
    render=_spinner,
    cross={"size": ["1", "2", "3"], "holds": ["none", "words", "box"]},
    sweep={
        "size": {"responsive": RESPONSIVE},
        # Without children a spinner that is not loading renders nothing.
        "loading": [True],
        "inside": ["colored"],
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        # Around words alone, a spinner that is not loading is no element.
        {"holds": ["box"], "loading": [True, False]},
        {"holds": ["none", "words"], "appearance": [DARK]},
        {"size": {"responsive": RESPONSIVE}, "viewport": [520, 800, 1100, 1280]},
    ],
    stage=(200, 100),
    # Not held to zero: the leaves are turned, and their edges are
    # anti-aliased by where the spinner is on the page.
    tolerance=0.002,
)

CONTRACT = Contract(
    component="spinner",
    render=lambda namespace: namespace.box(
        namespace.spinner(id="alone"),
        namespace.spinner("Report", id="over", size="3"),
        namespace.spinner("Ready", id="done", loading=False),
    ),
)


@CONTRACT.step("is a span of eight leaves in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    alone = run.server.element("alone")
    assert (alone.tag, alone.text) == ("span", "")
    assert run.server.text.count("Report") == 1
    assert run.server.text.count("Ready") == 1


@CONTRACT.step("shows its leaves with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    box = run.page.locator("#alone").bounding_box()
    assert box is not None
    assert (box["width"], box["height"]) == (16, 16)
    assert run.page.locator("#alone > span").count() == 8
    assert run.page.get_by_text("Ready").is_visible()


@CONTRACT.step("hides what it stands in for, which keeps its place", on=HYDRATED)
def _stands_in(run: Run) -> None:
    report = run.page.get_by_text("Report")
    assert report.evaluate("element => getComputedStyle(element).visibility") == (
        "hidden"
    )
    assert report.get_attribute("aria-hidden") == "true"
    assert run.page.get_by_text("Ready").is_visible()


@CONTRACT.step("each leaf fades in turn, eight to a turn of 800ms", on=HYDRATED)
def _animation(run: Run) -> None:
    leaves = run.page.evaluate(
        """() => [...document.querySelectorAll("#alone > span")].map((leaf) => {
            const [animation] = leaf.getAnimations();
            const timing = animation.effect.getTiming();
            return {
                frames: animation.effect.getKeyframes().map(
                    (frame) => [frame.offset, frame.opacity, frame.easing]),
                timing: [timing.duration, Math.round(timing.delay), timing.iterations,
                         timing.easing, timing.direction, timing.fill],
                state: animation.playState,
                transform: getComputedStyle(leaf).transform,
            };
        })"""
    )
    assert [leaf["frames"] for leaf in leaves] == [
        [[0, "1", "linear"], [1, "0.25", "linear"]]
    ] * 8
    assert [leaf["timing"] for leaf in leaves] == [
        [800, -100 * (8 - place), float("inf"), "linear", "normal", "none"]
        for place in range(8)
    ]
    assert [leaf["state"] for leaf in leaves] == ["running"] * 8
    assert len({leaf["transform"] for leaf in leaves}) == 8
