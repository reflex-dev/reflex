"""What the matrices of several components render and sweep."""

from __future__ import annotations

from typing import Any

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
