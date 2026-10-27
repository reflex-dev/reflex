"""Regression coverage for fixed-color layout demos staying readable in dark mode."""

import re
from pathlib import Path

import pytest

DOCS = Path(__file__).parents[2]

# Named CSS backgrounds the layout demos use; none of them adapt to the theme,
# so each box must pin its own text color instead of inheriting the theme's.
FIXED_BACKGROUND = re.compile(
    r'^(?P<indent>\s*)(?:bg|background_color)="(?:[a-z]+)",?\s*$', re.MULTILINE
)
INLINE_FIXED_BACKGROUND = re.compile(r'bg="[a-z]+"(?P<rest>[^)]*)\)')


@pytest.mark.parametrize(
    "doc",
    ["layout/stack.md", "layout/box.md", "layout/spacer.md", "layout/aspect_ratio.md"],
)
def test_fixed_color_boxes_pin_a_text_color(doc):
    """Every box with a fixed CSS background also sets an explicit text color."""
    source = (DOCS / "library" / doc).read_text()
    for match in FIXED_BACKGROUND.finditer(source):
        following = source[match.end() : match.end() + 200]
        assert re.match(r'\s*color="', following), (
            f"{doc}: {match.group(0).strip()} has no explicit text color"
        )
    for match in INLINE_FIXED_BACKGROUND.finditer(source):
        assert 'color="' in match.group("rest"), (
            f"{doc}: {match.group(0)} has no explicit text color"
        )
