"""Regression coverage for fixed-color layout demos staying readable in dark mode."""

import re
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[2]

# Named CSS backgrounds do not adapt to the theme, so a box using one must pin
# its own text color instead of inheriting the theme's foreground.
FIXED_BACKGROUND = re.compile(r'(?:bg|background_color)="[a-z]+"')


def enclosing_call(source: str, index: int) -> str:
    """Return the argument text of the component call that contains ``index``.

    Args:
        source: The document source.
        index: An offset inside the call's argument list.

    Returns:
        The text between the call's opening and closing parentheses.
    """
    depth = 0
    start = index
    while start > 0:
        start -= 1
        if source[start] == ")":
            depth += 1
        elif source[start] == "(":
            if depth == 0:
                break
            depth -= 1
    depth = 0
    end = start
    while end < len(source):
        end += 1
        if source[end] == "(":
            depth += 1
        elif source[end] == ")":
            if depth == 0:
                break
            depth -= 1
    return source[start + 1 : end]


@pytest.mark.parametrize(
    "doc",
    ["layout/stack.md", "layout/box.md", "layout/spacer.md", "layout/aspect_ratio.md"],
)
def test_fixed_color_boxes_pin_a_text_color(doc):
    """Every component with a fixed CSS background also sets an explicit text color."""
    source = (DOCS / "library" / doc).read_text()
    for match in FIXED_BACKGROUND.finditer(source):
        call = enclosing_call(source, match.start())
        assert re.search(r'\bcolor="', call), (
            f"{doc}: {match.group(0)} has no explicit text color in {call.strip()!r}"
        )
