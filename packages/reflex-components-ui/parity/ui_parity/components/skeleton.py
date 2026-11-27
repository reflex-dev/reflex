"""The skeleton: a pulsing block with the size of what it stands in for."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, LIGHT, Matrix

HOLDS = ["text", "words", "button", "soft-button", "avatar", "card", "nothing"]


def _skeleton(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a skeleton around what a cell says it holds.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``holds`` names the children.

    Returns:
        The skeleton, in a paragraph when it stands in for words of one.
    """
    props = dict(props)
    holds = props.pop("holds", "text")
    if holds == "text":
        return namespace.skeleton(namespace.text("Loading the report"), **props)
    if holds == "words":
        return namespace.text(
            "Total: ", namespace.skeleton("1,204 euros", **props), " this month."
        )
    if holds == "button":
        return namespace.skeleton(namespace.button("Save"), **props)
    if holds == "soft-button":
        return namespace.skeleton(
            namespace.button("Save", variant="classic", size="3"), **props
        )
    if holds == "avatar":
        return namespace.skeleton(namespace.avatar(fallback="AB", size="5"), **props)
    if holds == "card":
        return namespace.skeleton(
            namespace.card(namespace.text("Invoice"), namespace.button("Pay")), **props
        )
    return namespace.skeleton(**props)


MATRIX = Matrix(
    component="skeleton",
    render=_skeleton,
    # A skeleton that holds nothing and is not loading renders nothing.
    cross={"holds": HOLDS[:-1], "loading": [True, False]},
    sweep={
        "width": {
            "fixed": "120px",
            "responsive": rx.breakpoints(initial="60px", sm="160px"),
        },
        "height": ["40px"],
        "min_width": ["150px"],
        "max_width": ["40px"],
        "min_height": ["60px"],
        "max_height": ["8px"],
        "holds": ["nothing"],
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        {"holds": HOLDS, "appearance": [LIGHT, DARK]},
        {"holds": ["nothing", "button"], "width": ["120px"], "height": ["40px"]},
        {
            "holds": ["nothing", "text"],
            "width": {"responsive": rx.breakpoints(initial="60px", sm="160px")},
            "viewport": [520, 800, 1280],
        },
    ],
    stage=(260, 120),
    # A screenshot is taken with animations off, so the pulse is in no
    # image: the color of the skeleton is compared as a computed style, in
    # which both systems are on the same frame, and by the contract.
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="skeleton",
    render=lambda namespace: namespace.box(
        namespace.skeleton(namespace.button("Save", id="save")),
        namespace.text("Total: ", namespace.skeleton("1,204", id="words")),
        namespace.skeleton(namespace.button("Ready", id="ready"), loading=False),
        namespace.button("Last", id="last"),
    ),
)


@CONTRACT.step("is its child, or a span around text, in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    save = run.server.element("save")
    assert (save.tag, save.text) == ("button", "Save")
    assert save.attributes["aria-hidden"] == "true"
    assert save.attributes["tabindex"] == "-1"
    words = run.server.element("words")
    assert (words.tag, words.text) == ("span", "1,204")
    assert run.server.element("ready").text == "Ready"


@CONTRACT.step(
    "hides what is loading and shows what is not without JavaScript", on=NO_JAVASCRIPT
)
def _without_javascript(run: Run) -> None:
    _hides_what_is_loading(run)


@CONTRACT.step(
    "hides what is loading from the eye, the keyboard and a reader", on=HYDRATED
)
def _hydrated(run: Run) -> None:
    _hides_what_is_loading(run)
    assert run.page.get_by_role("button").evaluate_all(
        "buttons => buttons.map((button) => button.id)"
    ) == ["ready", "last"]
    focused = []
    for _ in range(2):
        run.page.keyboard.press("Tab")
        focused.append(run.page.evaluate("document.activeElement.id"))
    assert focused == ["ready", "last"]


@CONTRACT.step("pulses between two grays, back and forth every second", on=HYDRATED)
def _animation(run: Run) -> None:
    animation = run.page.evaluate(
        """() => {
            const [animation] = document.getElementById("words").getAnimations();
            const timing = animation.effect.getTiming();
            return {
                frames: animation.effect.getKeyframes().map(
                    (frame) => [frame.offset, frame.easing]),
                colors: animation.effect.getKeyframes().map(
                    (frame) => frame.backgroundColor).length,
                timing: [timing.duration, timing.delay, timing.iterations,
                         timing.easing, timing.direction, timing.fill],
                state: animation.playState,
            };
        }"""
    )
    assert animation == {
        "frames": [[0, "ease"], [1, "ease"]],
        "colors": 2,
        "timing": [1000, 0, float("inf"), "linear", "alternate-reverse", "none"],
        "state": "running",
    }


def _hides_what_is_loading(run: Run) -> None:
    """Check that a skeleton shows a block where its child is, and no text.

    Args:
        run: The run of the step.
    """
    styles = run.page.evaluate(
        """() => ["save", "words"].map((id) => {
            const style = getComputedStyle(document.getElementById(id));
            return [style.color, style.pointerEvents, style.backgroundImage];
        })"""
    )
    assert styles == [["rgba(0, 0, 0, 0)", "none", "none"]] * 2
    assert run.page.locator("#ready").is_visible()
    box = run.page.locator("#save").bounding_box()
    assert box is not None
    assert box["height"] == 32
