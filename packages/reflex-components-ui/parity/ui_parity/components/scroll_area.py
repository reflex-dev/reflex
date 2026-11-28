"""The scroll area: a box that scrolls what does not fit, natively in rx.ui."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix

# What an area holds, by how it overflows a frame of 208 by 88 pixels.
CONTENT = {
    "fits": (120, 40),
    "tall": (120, 300),
    "wide": (500, 40),
    "large": (500, 300),
}

# The keys that scroll a focused box down, the last one to its end.
SCROLL_KEYS = ["ArrowDown", "Space", "PageDown", "End"]

# The scroller of an area: the area itself in rx.ui, its viewport in Radix.
SCROLLER = """(area) => [area, ...area.querySelectorAll("*")].find((element) => {
    const style = getComputedStyle(element);
    return /auto|scroll/.test(style.overflowY + style.overflowX);
})"""


def _block(width: int, height: int) -> Any:
    """Create something to scroll: stripes of a fixed size.

    Args:
        width: Its width, in pixels.
        height: Its height, in pixels.

    Returns:
        The element.
    """
    return rx.el.div(
        style={
            "width": f"{width}px",
            "height": f"{height}px",
            "background_image": (
                "repeating-linear-gradient(135deg, rgb(200, 200, 220) 0 10px, "
                "rgb(120, 120, 180) 10px 20px)"
            ),
        },
    )


def _scroll_area(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a scroll area around stripes that fit or overflow.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``content`` names what the area holds.

    Returns:
        The scroll area.
    """
    props = dict(props)
    content = props.pop("content", "fits")
    return namespace.scroll_area(_block(*CONTENT[content]), **props)


SCROLLBARS = ["vertical", "horizontal", "both"]
TYPES = ["auto", "always", "scroll", "hover"]

MATRIX = Matrix(
    component="scroll_area",
    render=_scroll_area,
    cross={"scrollbars": SCROLLBARS, "type": TYPES},
    sweep={
        "content": ["tall", "wide", "large"],
        "scroll_hide_delay": [100],
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        # Not `auto` around what overflows: Radix Themes then shows its
        # scrollbars once it has measured the content, some time after the
        # page is ready, so a screenshot has them or not.
        {
            "content": ["tall", "wide", "large"],
            "scrollbars": SCROLLBARS,
            "type": ["always", "scroll", "hover"],
        },
        {"content": ["large"], "appearance": [DARK]},
    ],
    crop="stage",
    # Held to zero wherever no scrollbar shows. Where Radix Themes draws its
    # own scrollbars, the area of rx.ui has the ones of the browser, which
    # the allowlist says: in this browser they lie over the content and show
    # while it scrolls, so a cell at rest has none.
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="scroll_area",
    render=lambda namespace: rx.el.div(
        namespace.scroll_area(
            rx.el.p("First line", id="first"),
            _block(600, 600),
            rx.el.p("Last line", id="last"),
        ),
        id="area",
        style={"width": "200px", "height": "150px"},
    ),
)


def _scroll_offsets(run: Run) -> list[int]:
    """Read how far the area is scrolled.

    Args:
        run: The run of the step.

    Returns:
        The offsets of its scroller, from the left and from the top.
    """
    return run.page.locator("#area").evaluate(
        f"(area) => {{ const scroller = ({SCROLLER})(area);"
        " return [Math.round(scroller.scrollLeft), Math.round(scroller.scrollTop)]; }"
    )


@CONTRACT.step("holds all its content in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    assert run.server.element("area").tag == "div"
    assert run.server.element("first").text == "First line"
    assert run.server.element("last").text == "Last line"


@CONTRACT.step("scrolls to its last line with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    run.page.locator("#last").wait_for(state="attached")
    run.page.locator("#area").hover()
    reached = (
        "document.getElementById('last').getBoundingClientRect().bottom"
        " <= document.getElementById('area').getBoundingClientRect().bottom + 1"
    )
    # A wheel turned before the browser can hit-test the page scrolls nothing,
    # so turn it until the area has moved: only the end of the scroll is asserted.
    for _ in range(40):
        run.page.mouse.wheel(0, 2000)
        try:
            run.page.wait_for_function(reached, timeout=250)
        except PlaywrightTimeoutError:
            continue
        return
    run.page.wait_for_function(reached, timeout=1)


@CONTRACT.step("the wheel scrolls it both ways", on=HYDRATED)
def _wheel(run: Run) -> None:
    assert _scroll_offsets(run) == [0, 0]
    run.page.locator("#area").hover()
    run.page.mouse.wheel(120, 80)
    run.page.wait_for_function(
        f"(() => {{ const scroller = ({SCROLLER})(document.getElementById('area'));"
        " return scroller.scrollLeft === 120 && scroller.scrollTop === 80; })()"
    )


@CONTRACT.step("Tab reaches it and the keyboard scrolls it", on=HYDRATED)
def _keyboard(run: Run) -> None:
    run.page.keyboard.press("Tab")
    assert run.page.locator("#area").evaluate(
        f"(area) => ({SCROLLER})(area) === document.activeElement"
    )
    # Every key a browser scrolls a focused box with, each from the top: the
    # ones that did not move it are named when the step fails.
    scrolled = (
        f"(() => {{ const scroller = ({SCROLLER})(document.getElementById('area'));"
        " return scroller.scrollTop > 0; })()"
    )
    moved = []
    for key in SCROLL_KEYS:
        run.page.locator("#area").evaluate(
            f"(area) => ({SCROLLER})(area).scrollTo({{top: 0, behavior: 'instant'}})"
        )
        run.page.keyboard.press(key)
        try:
            run.page.wait_for_function(scrolled, timeout=2000)
        except PlaywrightTimeoutError:
            continue
        moved.append(key)
    assert moved == SCROLL_KEYS
    # And back to the top, from the end the last key went to.
    run.page.keyboard.press("Home")
    run.page.wait_for_function(
        f"({SCROLLER})(document.getElementById('area')).scrollTop === 0"
    )
