"""The Cond page's demo text stays readable in both themes."""

import ast
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2]
COND = DOCS / "library" / "dynamic-rendering" / "cond.md"
PYTHON_BLOCK = re.compile(r"^```python[^\n]*\n(.*?)^```", re.DOTALL | re.MULTILINE)
# Radix step 11 is the text step designed to read on both themes' backgrounds.
THEME_TEXT = re.compile(r"var\(--[a-z]+-11\)")


def _colors(source: str) -> list[str]:
    """Collect every string passed as a ``color`` argument in the page's examples.

    Args:
        source: The page's Markdown source.

    Returns:
        The colors, in source order.
    """
    return [
        keyword.value.value
        for block in PYTHON_BLOCK.findall(source)
        for node in ast.walk(ast.parse(block))
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "color"
        and isinstance(keyword.value, ast.Constant)
        and isinstance(keyword.value.value, str)
    ]


def test_color_collection_sees_every_call_shape():
    """Parentheses inside the text and single quotes do not hide a color."""
    source = (
        "```python\n"
        'rx.text("Text (optional)", color="blue")\n'
        "rx.text('x', color='red')\n"
        "rx.cond(flag, rx.text(f'{n} items', color='green'))\n"
        "```\n"
    )
    assert _colors(source) == ["blue", "red", "green"]


def test_cond_demo_text_uses_theme_aware_colors():
    """Fixed CSS colors such as blue fall below 4.5:1 on the dark theme."""
    colors = _colors(COND.read_text())
    assert colors, "expected colored text in the Cond demos"
    fixed = [color for color in colors if not THEME_TEXT.fullmatch(color)]
    assert not fixed, f"Cond demo text uses fixed colors: {fixed}"
