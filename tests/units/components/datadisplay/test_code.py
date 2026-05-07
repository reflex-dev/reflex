import pytest
from reflex_components_code.code import CodeBlock, Theme

import reflex as rx


@pytest.mark.parametrize(
    ("theme", "expected"),
    [(Theme.one_light, "oneLight"), (Theme.one_dark, "oneDark")],
)
def test_code_light_dark_theme(theme, expected):
    code_block = CodeBlock.create(theme=theme)

    assert code_block.theme._js_expr == expected  # pyright: ignore [reportAttributeAccessIssue]


def test_code_block_rejects_string_theme():
    with pytest.raises(TypeError, match=r"CodeBlock\.theme"):
        CodeBlock.create("print('Hello')", theme="one_dark")  # pyright: ignore[reportArgumentType]


def test_code_block_accepts_color_mode_cond_theme():
    theme = rx.color_mode_cond(
        light=rx.code_block.themes.one_light,
        dark=rx.code_block.themes.one_dark,
    )
    code_block = CodeBlock.create("print('Hello')", theme=theme)

    rendered = code_block.render()
    style_prop = next((p for p in rendered["props"] if p.startswith("style:")), None)
    assert style_prop is not None, "code block did not render a style prop"
    assert "resolvedColorMode" in style_prop
    assert "oneLight" in style_prop
    assert "oneDark" in style_prop

    imports = code_block._get_all_imports()
    assert "react-syntax-highlighter/dist/esm/styles/prism/one-light" in imports
    assert "react-syntax-highlighter/dist/esm/styles/prism/one-dark" in imports
