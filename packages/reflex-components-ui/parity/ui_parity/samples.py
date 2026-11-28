"""What the matrices of several components render and sweep."""

from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

import reflex as rx

# Every accent color, for a sweep of `color_scheme`.
ACCENTS: tuple[str, ...] = (
    "tomato",
    "red",
    "ruby",
    "crimson",
    "pink",
    "plum",
    "purple",
    "violet",
    "iris",
    "indigo",
    "blue",
    "cyan",
    "teal",
    "jade",
    "green",
    "grass",
    "brown",
    "orange",
    "sky",
    "mint",
    "lime",
    "yellow",
    "amber",
    "gold",
    "bronze",
    "gray",
)

# Long enough to wrap over several lines in a frame.
PARAGRAPH = (
    "The quick brown fox jumps over the lazy dog, then naps in the warm afternoon sun."
)

WORDS = ("The", "quick", "brown", "fox", "jumps", "over", "lazy")


def tiles(words: tuple[str, ...] = WORDS) -> list[Any]:
    """Create the children of a layout: boxes with an outline, one per word.

    Args:
        words: The text of each box.

    Returns:
        The boxes, the same elements for both systems.
    """
    return [
        rx.el.div(
            word,
            style={"border": "1px solid currentColor", "padding": "2px 6px"},
        )
        for word in words
    ]


def focused(page: Any) -> str:
    """Read which element of a page has the focus.

    Args:
        page: The page.

    Returns:
        The id of the element.
    """
    return page.evaluate("document.activeElement.id")


def wait_for_text(page: Any, element: str, text: str) -> None:
    """Wait until an element of a page holds a text.

    Args:
        page: The page.
        element: The id of the element.
        text: Its whole text.
    """
    page.wait_for_function(
        "([id, text]) => document.getElementById(id).textContent === text",
        arg=[element, text],
    )


def wait_for_value(
    page: Any, expression: str, expected: Any, timeout: float = 5000
) -> None:
    """Wait until a JavaScript expression of a page has a value.

    A step that waits says what it found when the wait ends without it,
    where a timeout alone says nothing of what the component did.

    Args:
        page: The page.
        expression: The expression: what it evaluates to is compared as JSON.
        expected: Its value.
        timeout: How long to wait, in milliseconds.

    Raises:
        AssertionError: If the expression does not come to have the value,
            with the value it has.
    """
    try:
        page.wait_for_function(
            f"expected => JSON.stringify({expression}) === expected",
            arg=json.dumps(expected, separators=(",", ":"), ensure_ascii=False),
            timeout=timeout,
        )
    except PlaywrightTimeoutError:
        actual = page.evaluate(expression)
        if actual != expected:
            msg = f"{expression} is {actual!r}, not {expected!r}"
            raise AssertionError(msg) from None
