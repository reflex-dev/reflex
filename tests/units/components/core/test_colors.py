import pytest

import reflex as rx
from reflex.components.datadisplay.code import CodeBlock
from reflex.constants.colors import Color
from reflex.constants.state import FIELD_MARKER
from reflex.vars.base import LiteralVar


class ColorState(rx.State):
    """Test color state."""

    color: rx.Field[str] = rx.field("mint")
    color_part: rx.Field[str] = rx.field("tom")
    shade: rx.Field[int] = rx.field(4)
    alpha: rx.Field[bool] = rx.field(False)


color_state_name = ColorState.get_full_name().replace(".", "__")


def create_color_var(color):
    return LiteralVar.create(color)


color_with_fstring = rx.color(
    f"{ColorState.color}",  # pyright: ignore [reportArgumentType]
    ColorState.shade,
)


@pytest.mark.parametrize(
    ("color", "expected", "expected_type"),
    [
        (create_color_var(rx.color("mint")), '"var(--mint-7)"', Color),
        (create_color_var(rx.color("mint", 3)), '"var(--mint-3)"', Color),
        (create_color_var(rx.color("mint", 3, True)), '"var(--mint-a3)"', Color),
        (
            create_color_var(rx.color(ColorState.color, ColorState.shade)),
            f'("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-"+(((__to_string) => __to_string.toString())({color_state_name!s}.shade{FIELD_MARKER}))+")")',
            Color,
        ),
        (
            create_color_var(
                rx.color(ColorState.color, ColorState.shade, ColorState.alpha)
            ),
            f'("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-"+({color_state_name!s}.alpha{FIELD_MARKER} ? "a" : "")+(((__to_string) => __to_string.toString())({color_state_name!s}.shade{FIELD_MARKER}))+")")',
            Color,
        ),
        (
            create_color_var(color_with_fstring),
            f'("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-"+(((__to_string) => __to_string.toString())({color_state_name!s}.shade{FIELD_MARKER}))+")")',
            Color,
        ),
        (
            create_color_var(
                rx.color(
                    f"{ColorState.color_part}ato",  # pyright: ignore [reportArgumentType]
                    ColorState.shade,
                )
            ),
            f'("var(--"+({color_state_name!s}.color_part{FIELD_MARKER}+"ato")+"-"+(((__to_string) => __to_string.toString())({color_state_name!s}.shade{FIELD_MARKER}))+")")',
            Color,
        ),
        (
            create_color_var(f"{rx.color(ColorState.color, ColorState.shade)}"),
            f'("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-"+{color_state_name!s}.shade{FIELD_MARKER}+")")',
            str,
        ),
        (
            create_color_var(f"{color_with_fstring}"),
            f'("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-"+{color_state_name!s}.shade{FIELD_MARKER}+")")',
            str,
        ),
    ],
)
def test_color(color, expected, expected_type: type[str] | type[Color]):
    assert color._var_type is expected_type
    assert str(color) == expected


@pytest.mark.parametrize(
    ("cond_var", "expected"),
    [
        (
            rx.cond(True, rx.color("mint"), rx.color("tomato", 5)),
            '(true ? "var(--mint-7)" : "var(--tomato-5)")',
        ),
        (
            rx.cond(True, rx.color(ColorState.color), rx.color(ColorState.color, 5)),
            f'(true ? ("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-7)") : ("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-5)"))',
        ),
        (
            rx.match(
                "condition",
                ("first", rx.color("mint")),
                ("second", rx.color("tomato", 5)),
                rx.color(ColorState.color, 2),
            ),
            (
                '(() => { switch (JSON.stringify("condition")) {case JSON.stringify("first"):  return ("var(--mint-7)");'
                '  break;case JSON.stringify("second"):  return ("var(--tomato-5)");  break;default:  '
                f'return (("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-2)"));  break;}};}})()'
            ),
        ),
        (
            rx.match(
                "condition",
                ("first", rx.color(ColorState.color)),
                ("second", rx.color(ColorState.color, 5)),
                rx.color(ColorState.color, 2),
            ),
            (
                '(() => { switch (JSON.stringify("condition")) {case JSON.stringify("first"):  '
                f'return (("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-7)"));  break;case JSON.stringify("second"):  '
                f'return (("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-5)"));  break;default:  '
                f'return (("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-2)"));  break;}};}})()'
            ),
        ),
    ],
)
def test_color_with_conditionals(cond_var, expected):
    assert str(cond_var) == expected


@pytest.mark.parametrize(
    ("color", "expected"),
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
    assert str(code_block.custom_style["backgroundColor"]) == expected  # pyright: ignore [reportAttributeAccessIssue]
