from typing import Type, Union

import pytest

import reflex as rx
from reflex.components.datadisplay.code import CodeBlock
from reflex.constants.colors import Color
from reflex.vars.base import LiteralVar


class ColorState(rx.State):
    """Test color state."""

    color: str = "mint"
    color_part: str = "tom"
    shade: int = 4


color_state_name = ColorState.get_full_name().replace(".", "__")


def create_color_var(color):
    return LiteralVar.create(color)


@pytest.mark.parametrize(
    "color, expected, expected_type",
    [
        (create_color_var(rx.color("mint")), '"var(--mint-7)"', Color),
        (create_color_var(rx.color("mint", 3)), '"var(--mint-3)"', Color),
        (create_color_var(rx.color("mint", 3, True)), '"var(--mint-a3)"', Color),
        (
            create_color_var(rx.color(ColorState.color, ColorState.shade)),  # type: ignore
            f'("var(--"+{str(color_state_name)}.color+"-"+{str(color_state_name)}.shade+")")',
            Color,
        ),
        (
            create_color_var(rx.color(f"{ColorState.color}", f"{ColorState.shade}")),  # type: ignore
            f'("var(--"+{str(color_state_name)}.color+"-"+{str(color_state_name)}.shade+")")',
            Color,
        ),
        (
            create_color_var(
                rx.color(f"{ColorState.color_part}ato", f"{ColorState.shade}")  # type: ignore
            ),
            f'("var(--"+{str(color_state_name)}.color_part+"ato-"+{str(color_state_name)}.shade+")")',
            Color,
        ),
        (
            create_color_var(f'{rx.color(ColorState.color, f"{ColorState.shade}")}'),  # type: ignore
            f'("var(--"+{str(color_state_name)}.color+"-"+{str(color_state_name)}.shade+")")',
            str,
        ),
        (
            create_color_var(
                f'{rx.color(f"{ColorState.color}", f"{ColorState.shade}")}'  # type: ignore
            ),
            f'("var(--"+{str(color_state_name)}.color+"-"+{str(color_state_name)}.shade+")")',
            str,
        ),
    ],
)
def test_color(color, expected, expected_type: Union[Type[str], Type[Color]]):
    assert color._var_type is expected_type
    assert str(color) == expected


@pytest.mark.parametrize(
    "cond_var, expected",
    [
        (
            rx.cond(True, rx.color("mint"), rx.color("tomato", 5)),
            '(true ? "var(--mint-7)" : "var(--tomato-5)")',
        ),
        (
            rx.cond(True, rx.color(ColorState.color), rx.color(ColorState.color, 5)),  # type: ignore
            f'(true ? ("var(--"+{str(color_state_name)}.color+"-7)") : ("var(--"+{str(color_state_name)}.color+"-5)"))',
        ),
        (
            rx.match(
                "condition",
                ("first", rx.color("mint")),
                ("second", rx.color("tomato", 5)),
                rx.color(ColorState.color, 2),  # type: ignore
            ),
            '(() => { switch (JSON.stringify("condition")) {case JSON.stringify("first"):  return ("var(--mint-7)");'
            '  break;case JSON.stringify("second"):  return ("var(--tomato-5)");  break;default:  '
            f'return (("var(--"+{str(color_state_name)}.color+"-2)"));  break;}};}})()',
        ),
        (
            rx.match(
                "condition",
                ("first", rx.color(ColorState.color)),  # type: ignore
                ("second", rx.color(ColorState.color, 5)),  # type: ignore
                rx.color(ColorState.color, 2),  # type: ignore
            ),
            '(() => { switch (JSON.stringify("condition")) {case JSON.stringify("first"):  '
            f'return (("var(--"+{str(color_state_name)}.color+"-7)"));  break;case JSON.stringify("second"):  '
            f'return (("var(--"+{str(color_state_name)}.color+"-5)"));  break;default:  '
            f'return (("var(--"+{str(color_state_name)}.color+"-2)"));  break;}};}})()',
        ),
    ],
)
def test_color_with_conditionals(cond_var, expected):
    assert str(cond_var) == expected


@pytest.mark.parametrize(
    "color, expected",
    [
        (create_color_var(rx.color("red")), '"var(--red-7)"'),
        (create_color_var(rx.color("green", shade=1)), '"var(--green-1)"'),
        (create_color_var(rx.color("blue", alpha=True)), '"var(--blue-a7)"'),
        ("red", '"red"'),
        ("green", '"green"'),
        ("blue", '"blue"'),
    ],
)
def test_radix_color(color, expected):
    """Test that custom_style can accept both string
    literals and rx.color inputs.

    Args:
        color (Color): A Color made with rx.color
        expected (str): The expected custom_style string, radix or literal
    """
    code_block = CodeBlock.create("Hello World", background_color=color)
    assert str(code_block.custom_style["backgroundColor"]) == expected  # type: ignore
