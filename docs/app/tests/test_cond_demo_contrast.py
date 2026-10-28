"""The Cond page's demo text stays readable in both themes."""

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2]
COND = DOCS / "library" / "dynamic-rendering" / "cond.md"
TEXT_COLOR = re.compile(r'rx\.text\([^()]*?color="(?P<color>[^"]+)"')
# Radix step 11 is the text step designed to read on both themes' backgrounds.
THEME_TEXT = re.compile(r"var\(--[a-z]+-11\)")


def test_cond_demo_text_uses_theme_aware_colors():
    """Fixed CSS colors such as blue fall below 4.5:1 on the dark theme."""
    colors = [match["color"] for match in TEXT_COLOR.finditer(COND.read_text())]
    assert colors, "expected colored text in the Cond demos"
    fixed = [color for color in colors if not THEME_TEXT.fullmatch(color)]
    assert not fixed, f"Cond demo text uses fixed colors: {fixed}"
