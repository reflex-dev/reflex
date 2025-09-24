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
        (
            create_color_var(rx.color("mint")),
            'Object.assign(new String("var(--mint-7)"), ({ ["color"] : "mint", ["alpha"] : false, ["shade"] : 7 }))',
            Color,
        ),
        (
            create_color_var(rx.color("mint", 3)),
            'Object.assign(new String("var(--mint-3)"), ({ ["color"] : "mint", ["alpha"] : false, ["shade"] : 3 }))',
            Color,
        ),
        (
            create_color_var(rx.color("mint", 3, True)),
            'Object.assign(new String("var(--mint-a3)"), ({ ["color"] : "mint", ["alpha"] : true, ["shade"] : 3 }))',
            Color,
        ),
        (
            create_color_var(rx.color(ColorState.color, ColorState.shade)),
            f'Object.assign(new String(("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-"+(((__to_string) => __to_string.toString())({color_state_name!s}.shade{FIELD_MARKER}))+")")), ({{ ["color"] : {color_state_name!s}.color{FIELD_MARKER}, ["alpha"] : false, ["shade"] : {color_state_name!s}.shade{FIELD_MARKER} }}))',
            Color,
        ),
        (
            create_color_var(
                rx.color(ColorState.color, ColorState.shade, ColorState.alpha)
            ),
            f'Object.assign(new String(("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-"+({color_state_name!s}.alpha{FIELD_MARKER} ? "a" : "")+(((__to_string) => __to_string.toString())({color_state_name!s}.shade{FIELD_MARKER}))+")")), ({{ ["color"] : {color_state_name!s}.color{FIELD_MARKER}, ["alpha"] : {color_state_name!s}.alpha{FIELD_MARKER}, ["shade"] : {color_state_name!s}.shade{FIELD_MARKER} }}))',
            Color,
        ),
        (
            create_color_var(color_with_fstring),
            f'Object.assign(new String(("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-"+(((__to_string) => __to_string.toString())({color_state_name!s}.shade{FIELD_MARKER}))+")")), ({{ ["color"] : {color_state_name!s}.color{FIELD_MARKER}, ["alpha"] : false, ["shade"] : {color_state_name!s}.shade{FIELD_MARKER} }}))',
            Color,
        ),
        (
            create_color_var(
                rx.color(
                    f"{ColorState.color_part}ato",  # pyright: ignore [reportArgumentType]
                    ColorState.shade,
                )
            ),
            f'Object.assign(new String(("var(--"+({color_state_name!s}.color_part{FIELD_MARKER}+"ato")+"-"+(((__to_string) => __to_string.toString())({color_state_name!s}.shade{FIELD_MARKER}))+")")), ({{ ["color"] : ({color_state_name!s}.color_part{FIELD_MARKER}+"ato"), ["alpha"] : false, ["shade"] : {color_state_name!s}.shade{FIELD_MARKER} }}))',
            Color,
        ),
        (
            create_color_var(f"{rx.color(ColorState.color, ColorState.shade)}"),
            f'Object.assign(new String(("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-"+(((__to_string) => __to_string.toString())({color_state_name!s}.shade{FIELD_MARKER}))+")")), ({{ ["color"] : {color_state_name!s}.color{FIELD_MARKER}, ["alpha"] : false, ["shade"] : {color_state_name!s}.shade{FIELD_MARKER} }}))',
            Color,
        ),
        (
            create_color_var(f"{color_with_fstring}"),
            f'Object.assign(new String(("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-"+(((__to_string) => __to_string.toString())({color_state_name!s}.shade{FIELD_MARKER}))+")")), ({{ ["color"] : {color_state_name!s}.color{FIELD_MARKER}, ["alpha"] : false, ["shade"] : {color_state_name!s}.shade{FIELD_MARKER} }}))',
            Color,
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
            '(true ? Object.assign(new String("var(--mint-7)"), ({ ["color"] : "mint", ["alpha"] : false, ["shade"] : 7 })) : Object.assign(new String("var(--tomato-5)"), ({ ["color"] : "tomato", ["alpha"] : false, ["shade"] : 5 })))',
        ),
        (
            rx.cond(True, rx.color(ColorState.color), rx.color(ColorState.color, 5)),
            f'(true ? Object.assign(new String(("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-7)")), ({{ ["color"] : {color_state_name!s}.color{FIELD_MARKER}, ["alpha"] : false, ["shade"] : 7 }})) : Object.assign(new String(("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-5)")), ({{ ["color"] : {color_state_name!s}.color{FIELD_MARKER}, ["alpha"] : false, ["shade"] : 5 }})))',
        ),
        (
            rx.match(
                "condition",
                ("first", rx.color("mint")),
                ("second", rx.color("tomato", 5)),
                rx.color(ColorState.color, 2),
            ),
            '(() => { switch (JSON.stringify("condition")) {case JSON.stringify("first"):  return (Object.assign(new String("var(--mint-7)"), ({ ["color"] : "mint", ["alpha"] : false, ["shade"] : 7 })));'
            '  break;case JSON.stringify("second"):  return (Object.assign(new String("var(--tomato-5)"), ({ ["color"] : "tomato", ["alpha"] : false, ["shade"] : 5 })));  break;default:  '
            f'return (Object.assign(new String(("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-2)")), ({{ ["color"] : {color_state_name!s}.color{FIELD_MARKER}, ["alpha"] : false, ["shade"] : 2 }})));  break;}};}})()',
        ),
        (
            rx.match(
                "condition",
                ("first", rx.color(ColorState.color)),
                ("second", rx.color(ColorState.color, 5)),
                rx.color(ColorState.color, 2),
            ),
            '(() => { switch (JSON.stringify("condition")) {case JSON.stringify("first"):  '
            f'return (Object.assign(new String(("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-7)")), ({{ ["color"] : {color_state_name!s}.color{FIELD_MARKER}, ["alpha"] : false, ["shade"] : 7 }})));  break;case JSON.stringify("second"):  '
            f'return (Object.assign(new String(("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-5)")), ({{ ["color"] : {color_state_name!s}.color{FIELD_MARKER}, ["alpha"] : false, ["shade"] : 5 }})));  break;default:  '
            f'return (Object.assign(new String(("var(--"+{color_state_name!s}.color{FIELD_MARKER}+"-2)")), ({{ ["color"] : {color_state_name!s}.color{FIELD_MARKER}, ["alpha"] : false, ["shade"] : 2 }})));  break;}};}})()',
        ),
    ],
)
def test_color_with_conditionals(cond_var, expected):
    assert str(cond_var) == expected


@pytest.mark.parametrize(
    ("color", "expected"),
    [
        (
            create_color_var(rx.color("red")),
            'Object.assign(new String("var(--red-7)"), ({ ["color"] : "red", ["alpha"] : false, ["shade"] : 7 }))',
        ),
        (
            create_color_var(rx.color("green", shade=1)),
            'Object.assign(new String("var(--green-1)"), ({ ["color"] : "green", ["alpha"] : false, ["shade"] : 1 }))',
        ),
        (
            create_color_var(rx.color("blue", alpha=True)),
            'Object.assign(new String("var(--blue-a7)"), ({ ["color"] : "blue", ["alpha"] : true, ["shade"] : 7 }))',
        ),
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
