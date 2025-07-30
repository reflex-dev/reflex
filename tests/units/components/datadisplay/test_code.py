import pytest

from reflex.components.datadisplay.code import CodeBlock, Theme


@pytest.mark.parametrize(
    ("theme", "expected"),
    [(Theme.one_light, "oneLight"), (Theme.one_dark, "oneDark")],
)
def test_code_light_dark_theme(theme, expected):
    code_block = CodeBlock.create(theme=theme)

    assert code_block.theme._js_expr == expected  # pyright: ignore [reportAttributeAccessIssue]
