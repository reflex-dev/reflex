"""Fixed-color demo palettes must remain readable independently of the theme."""

import ast
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2]
PYTHON_BLOCK = re.compile(r"^```python[^\n]*\n(.*?)^```", re.DOTALL | re.MULTILINE)


def _trees(path: str) -> list[ast.Module]:
    """Parse the Python examples in a documentation page."""
    return [
        ast.parse(block) for block in PYTHON_BLOCK.findall((DOCS / path).read_text())
    ]


def _contrast(first: str, second: str) -> float:
    """Return the WCAG contrast ratio of two opaque hexadecimal sRGB colors."""

    def luminance(color: str) -> float:
        channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        ]
        return sum(
            value * weight
            for value, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True)
        )

    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def test_foreach_swatch_palette_has_normal_text_contrast():
    """Every literal swatch, including nested dictionaries, supports its white label."""
    trees = _trees("library/dynamic-rendering/foreach.md")
    colors = {
        node.value
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and re.fullmatch(r"#[0-9A-Fa-f]{6}", node.value)
    }
    assert len(colors) == 6
    helper = next(
        node
        for tree in trees
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "color_swatch"
    )
    foregrounds = [
        ast.literal_eval(keyword.value)
        for node in ast.walk(helper)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "color"
    ]
    assert foregrounds == ["white"]
    assert {
        color: round(_contrast(color, "#FFFFFF"), 2)
        for color in colors
        if _contrast(color, "#FFFFFF") < 4.5
    } == {}


def test_styling_stack_pins_readable_foregrounds():
    """The four Stack boxes cannot inherit white text from the dark theme."""
    boxes = []
    for tree in _trees("styling/layout.md"):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            values = {
                keyword.arg: keyword.value.value
                for keyword in node.keywords
                if isinstance(keyword.value, ast.Constant)
            }
            if values.get("bg") in {"orange", "lightblue"}:
                boxes.append((values["bg"], values.get("color")))
    assert sorted(boxes) == [
        ("lightblue", "black"),
        ("lightblue", "black"),
        ("orange", "black"),
        ("orange", "black"),
    ]
    assert all(
        _contrast(background, "#000000") >= 4.5 for background in ("#FFA500", "#ADD8E6")
    )
