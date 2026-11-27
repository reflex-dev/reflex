"""Tests for reflex_components_ui.style.emit."""

from typing import Any

import pytest
from reflex_base.vars.base import Var
from reflex_components_ui.style import ComponentStyles, StyleError, merge
from reflex_components_ui.style.emit import Emitted, emit, inline

import reflex as rx

RUBY = "$/reflex-ui/colors/ruby.stylex.js"
JADE = "$/reflex-ui/colors/jade.stylex.js"


class EmitState(rx.State):
    """State the styles and the props are bound to."""

    width: rx.Field[str] = rx.field("320px")
    count: rx.Field[int] = rx.field(2)
    kind: rx.Field[str] = rx.field("solid")
    size: rx.Field[str] = rx.field("1")
    styles: rx.Field[dict[str, str]] = rx.field(default_factory=dict)


S = EmitState

# What the expected source names each Var by.
VARS = {
    "<width>": S.width,
    "<count>": S.count,
    "<kind>": S.kind,
    "<size>": S.size,
    "<styles>": S.styles,
    "<calc>": Var.create(f"calc({S.width} * 2)"),
    "<untyped>": Var("props.raw"),
    "<tone>": Var("props.tone", _var_type=str),
}

CARD: ComponentStyles = {
    "base": {
        "padding": "var(--space-3)",
        "border_radius": "var(--radius-4)",
        "box_shadow": "var(--shadow-2)",
    },
}

# Typed loosely: a variant unsets a property with None, which a user's style
# does not take.
BUTTON: dict[str, Any] = {
    "base": {"color": "black", "padding_top": "4px"},
    "variants": {
        "kind": {
            "solid": {"color": "white", "background_color": rx.color("ruby", 9)},
            "soft": {"opacity": 0.5, "padding_top": None},
        },
        "size": {"1": {"height": "1em"}, "2": {"height": "2em"}},
        "tone": {"warm": {"outline_color": "red"}},
    },
    "compound": [
        {"props": {"kind": "solid", "size": "2"}, "style": {"font_weight": 700}},
    ],
}

# A variant whose style holds a value bound to state.
SIZED: ComponentStyles = {
    "variants": {"kind": {"a": {"width": S.width}, "b": {"width": "1px"}}},
}

NO_STYLES: ComponentStyles = {}


def js(source: str) -> str:
    """Write the expression of each Var into expected source.

    Args:
        source: Source that names Vars as in ``VARS``.

    Returns:
        The source as it is emitted.
    """
    for name, var in VARS.items():
        source = source.replace(name, str(var))
    return source


def emitted(
    declaration: str | None = None,
    classes: str | None = None,
    lookups: tuple[str, ...] = (),
    variables: tuple[str, ...] = (),
    inline: str | None = None,
    imports: tuple[str, ...] = (),
    vars: tuple[str, ...] = (),
) -> tuple[Any, ...]:
    """Describe an expected result, with every Var named as in ``VARS``.

    Args:
        declaration: The module-level statements.
        classes: The constant holding the class names every instance has.
        lookups: The expressions that give the class names of bound props.
        variables: The entries of the inline style.
        inline: The Var spread into the inline style.
        imports: The modules imported for their CSS.
        vars: The Vars the element reads.

    Returns:
        What ``comparable`` makes of the result.
    """
    return (
        declaration,
        classes,
        tuple([js(lookup) for lookup in lookups]),
        tuple([js(variable) for variable in variables]),
        None if inline is None else js(inline),
        imports,
        tuple([js(var) for var in vars]),
    )


def comparable(result: Emitted) -> tuple[Any, ...]:
    """Reduce a result to values that compare: a Var does not.

    Args:
        result: What ``emit`` returned.

    Returns:
        Its fields, each Var replaced by its expression.
    """
    return (
        result.declaration,
        result.classes,
        result.lookups,
        result.variables,
        None if result.inline is None else str(result.inline),
        result.imports,
        tuple([str(var) for var in result.vars]),
    )


# The style table, the props, the style and the layout props of an element,
# and what is emitted for it. One group for each kind of input.
CASES: dict[str, tuple[dict[str, Any], tuple[Any, ...]]] = {
    "nothing": ({"styles": NO_STYLES}, emitted()),
    "literal": (
        {
            "styles": CARD,
            "style": {"width": "320px", "z_index": 2, "line_height": 1.5},
        },
        emitted(
            declaration=(
                'const sx_283e421a96 = stylex.create({ s: {"paddingTop": '
                '"var(--space-3)", "paddingRight": "var(--space-3)", '
                '"paddingBottom": "var(--space-3)", "paddingLeft": '
                '"var(--space-3)", "borderTopLeftRadius": "var(--radius-4)", '
                '"borderTopRightRadius": "var(--radius-4)", '
                '"borderBottomRightRadius": "var(--radius-4)", '
                '"borderBottomLeftRadius": "var(--radius-4)", "boxShadow": '
                '"var(--shadow-2)", "width": "320px", "zIndex": 2, '
                '"lineHeight": 1.5} });\n'
                "const sx_283e421a96_c = "
                "stylex.props(sx_283e421a96.s).className;"
            ),
            classes="sx_283e421a96_c",
            imports=(
                "$/reflex-ui/tokens/radius.stylex.js",
                "$/reflex-ui/tokens/shadow.stylex.js",
                "$/reflex-ui/tokens/space.stylex.js",
            ),
        ),
    ),
    # The card of the plan: its width bound to state, and a hover shadow.
    "var": (
        {
            "styles": CARD,
            "style": {
                "width": S.width,
                "_hover": {"box_shadow": "var(--shadow-3)"},
            },
        },
        emitted(
            declaration=(
                'const sx_75ce444dca = stylex.create({ s: {"paddingTop": '
                '"var(--space-3)", "paddingRight": "var(--space-3)", '
                '"paddingBottom": "var(--space-3)", "paddingLeft": '
                '"var(--space-3)", "borderTopLeftRadius": "var(--radius-4)", '
                '"borderTopRightRadius": "var(--radius-4)", '
                '"borderBottomRightRadius": "var(--radius-4)", '
                '"borderBottomLeftRadius": "var(--radius-4)", "boxShadow": '
                '{"default": "var(--shadow-2)", ":hover": "var(--shadow-3)"}, '
                '"width": "var(--v0)"} });\n'
                "const sx_75ce444dca_c = "
                "stylex.props(sx_75ce444dca.s).className;"
            ),
            classes="sx_75ce444dca_c",
            imports=(
                "$/reflex-ui/tokens/radius.stylex.js",
                "$/reflex-ui/tokens/shadow.stylex.js",
                "$/reflex-ui/tokens/space.stylex.js",
            ),
            variables=('"--v0": (<width>) ?? "initial"',),
            vars=("<width>",),
        ),
    ),
    # A number is a length except where CSS takes a bare number, and one Var
    # is one custom property wherever it reads the same.
    "var_number": (
        {
            "styles": NO_STYLES,
            "style": {
                "width": S.count,
                "opacity": S.count,
                "height": S.count,
                "margin_top": f"calc({S.width} * 2)",
                "_hover": {"width": S.count},
            },
        },
        emitted(
            declaration=(
                'const sx_545699866d = stylex.create({ s: {"width": {"default": '
                '"var(--v0)", ":hover": "var(--v0)"}, "opacity": "var(--v1)", '
                '"height": "var(--v0)", "marginTop": "var(--v2)"} });\n'
                "const sx_545699866d_c = stylex.props(sx_545699866d.s).className;"
            ),
            classes="sx_545699866d_c",
            variables=(
                '"--v0": (<count>) + "px"',
                '"--v1": (<count>) ?? "initial"',
                '"--v2": (("calc("+<width>+" * 2)")) ?? "initial"',
            ),
            vars=(
                "<count>",
                "<count>",
                '("calc("+<width>+" * 2)")',
            ),
        ),
    ),
    "var_untyped": (
        {
            "styles": NO_STYLES,
            "style": {"width": VARS["<untyped>"], "z_index": VARS["<untyped>"]},
        },
        emitted(
            declaration=(
                'const sx_bea9985a2e = stylex.create({ s: {"width": "var(--v0)", '
                '"zIndex": "var(--v1)"} });\n'
                "const sx_bea9985a2e_c = stylex.props(sx_bea9985a2e.s).className;"
            ),
            classes="sx_bea9985a2e_c",
            variables=(
                (
                    '"--v0": ((v) => typeof v === "number" ? v + "px" : v)(<untyped>) ?? '
                    '"initial"'
                ),
                '"--v1": (<untyped>) ?? "initial"',
            ),
            vars=(
                "<untyped>",
                "<untyped>",
            ),
        ),
    ),
    "hover": (
        {
            "styles": NO_STYLES,
            "style": {
                "color": "red",
                "_hover": {"color": "blue"},
                ":focus-visible": {"outline_width": "2px"},
            },
        },
        emitted(
            declaration=(
                'const sx_20caa62f24 = stylex.create({ s: {"color": {"default": '
                '"red", ":hover": "blue"}, "outlineWidth": {":focus-visible": '
                '"2px"}} });\n'
                "const sx_20caa62f24_c = stylex.props(sx_20caa62f24.s).className;"
            ),
            classes="sx_20caa62f24_c",
        ),
    ),
    "responsive": (
        {
            "styles": NO_STYLES,
            "style": {
                "width": ["100%", "50%"],
                "color": rx.breakpoints(initial="red", md="blue"),
            },
        },
        emitted(
            declaration=(
                'const sx_efb6e842bc = stylex.create({ s: {"width": {"default": '
                '"100%", "@media screen and (min-width: 30em)": "50%"}, "color": '
                '{"default": "red", "@media screen and (min-width: 62em)": "blue"}} '
                "});\n"
                "const sx_efb6e842bc_c = stylex.props(sx_efb6e842bc.s).className;"
            ),
            classes="sx_efb6e842bc_c",
        ),
    ),
    "color": (
        {
            "styles": NO_STYLES,
            "style": {
                "color": rx.color("ruby", 9),
                "_hover": {"background_color": rx.color("jade", 3)},
            },
        },
        emitted(
            declaration=(
                'const sx_fe91e1112f = stylex.create({ s: {"color": "var(--ruby-9)", '
                '"backgroundColor": {":hover": "var(--jade-3)"}} });\n'
                "const sx_fe91e1112f_c = stylex.props(sx_fe91e1112f.s).className;"
            ),
            classes="sx_fe91e1112f_c",
            imports=(
                JADE,
                RUBY,
            ),
        ),
    ),
    "layout": (
        {
            "styles": NO_STYLES,
            "layout": {
                "gap": "3",
                "p": ["1", "2"],
                "m": "-2",
                "columns": "3",
                "direction": "column",
            },
        },
        emitted(
            declaration=(
                'const sx_dae5511f98 = stylex.create({ s: {"rowGap": '
                '"var(--space-3)", "columnGap": "var(--space-3)", "paddingTop":'
                ' {"default": "var(--space-1)", "@media screen and (min-width: '
                '30em)": "var(--space-2)"}, "paddingRight": {"default": '
                '"var(--space-1)", "@media screen and (min-width: 30em)": '
                '"var(--space-2)"}, "paddingBottom": {"default": '
                '"var(--space-1)", "@media screen and (min-width: 30em)": '
                '"var(--space-2)"}, "paddingLeft": {"default": '
                '"var(--space-1)", "@media screen and (min-width: 30em)": '
                '"var(--space-2)"}, "marginTop": "calc(-1 * var(--space-2))", '
                '"marginRight": "calc(-1 * var(--space-2))", "marginBottom": '
                '"calc(-1 * var(--space-2))", "marginLeft": "calc(-1 * '
                'var(--space-2))", "gridTemplateColumns": "repeat(3, minmax(0, '
                '1fr))", "flexDirection": "column"} });\n'
                "const sx_dae5511f98_c = "
                "stylex.props(sx_dae5511f98.s).className;"
            ),
            classes="sx_dae5511f98_c",
            imports=("$/reflex-ui/tokens/space.stylex.js",),
        ),
    ),
    "shorthand": (
        {"styles": NO_STYLES, "style": {"margin": "0 auto"}},
        emitted(
            declaration=(
                'const sx_9cc5d777ce = stylex.create({ s: {"marginTop": "0", '
                '"marginRight": "auto", "marginBottom": "0", "marginLeft": "auto"} '
                "});\n"
                "const sx_9cc5d777ce_c = stylex.props(sx_9cc5d777ce.s).className;"
            ),
            classes="sx_9cc5d777ce_c",
        ),
    ),
    # Props known at compile time select their styles there.
    "variant_literal": (
        {"styles": BUTTON, "props": {"kind": "solid", "size": "2"}},
        emitted(
            declaration=(
                'const sx_6f8a31de05 = stylex.create({ s: {"color": "white", '
                '"paddingTop": "4px", "backgroundColor": "var(--ruby-9)", "height": '
                '"2em", "fontWeight": 700} });\n'
                "const sx_6f8a31de05_c = stylex.props(sx_6f8a31de05.s).className;"
            ),
            classes="sx_6f8a31de05_c",
            imports=(RUBY,),
        ),
    ),
    # One bound prop: a style for each of its values, holding the whole value
    # of what it changes, and the style of a value that is none of them.
    "variant_bound": (
        {
            "styles": BUTTON,
            "props": {"kind": S.kind, "size": "2"},
            "style": {"margin_top": "1px"},
        },
        emitted(
            declaration=(
                'const sx_097e4917a8 = stylex.create({ s: {"height": "2em", '
                '"marginTop": "1px"}, a0_0: {"color": "white", "paddingTop": "4px", '
                '"backgroundColor": "var(--ruby-9)", "fontWeight": 700}, a0_1: '
                '{"color": "black", "opacity": 0.5}, a0: {"color": "black", '
                '"paddingTop": "4px"} });\n'
                "const sx_097e4917a8_c = stylex.props(sx_097e4917a8.s).className;\n"
                'const sx_097e4917a8_0 = { __proto__: null, "solid": '
                'stylex.props(sx_097e4917a8.a0_0).className, "soft": '
                "stylex.props(sx_097e4917a8.a0_1).className };\n"
                "const sx_097e4917a8_0d = stylex.props(sx_097e4917a8.a0).className;"
            ),
            classes="sx_097e4917a8_c",
            lookups=("(sx_097e4917a8_0[<kind>] ?? sx_097e4917a8_0d)",),
            imports=(RUBY,),
            vars=("<kind>",),
        ),
    ),
    # A bound prop that changes nothing the element has without it.
    "variant_bound_adds": (
        {"styles": BUTTON, "props": {"kind": "soft", "tone": VARS["<tone>"]}},
        emitted(
            declaration=(
                'const sx_4dbc04f090 = stylex.create({ s: {"color": "black", '
                '"opacity": 0.5}, a0_0: {"outlineColor": "red"} });\n'
                "const sx_4dbc04f090_c = stylex.props(sx_4dbc04f090.s).className;\n"
                'const sx_4dbc04f090_0 = { __proto__: null, "warm": '
                "stylex.props(sx_4dbc04f090.a0_0).className };"
            ),
            classes="sx_4dbc04f090_c",
            lookups=('(sx_4dbc04f090_0[<tone>] ?? "")',),
            vars=("<tone>",),
        ),
    ),
    # Two bound props that a compound style combines are indexed together.
    "variant_bound_grouped": (
        {"styles": BUTTON, "props": {"kind": S.kind, "size": S.size}},
        emitted(
            declaration=(
                'const sx_954f5c8b18 = stylex.create({ a0_0: {"color": "white", '
                '"paddingTop": "4px", "backgroundColor": "var(--ruby-9)", "height": '
                '"1em"}, a0_1: {"color": "white", "paddingTop": "4px", '
                '"backgroundColor": "var(--ruby-9)", "height": "2em", "fontWeight": '
                '700}, a0_2: {"color": "black", "opacity": 0.5, "height": "1em"}, '
                'a0_3: {"color": "black", "opacity": 0.5, "height": "2em"}, a0: '
                '{"color": "black", "paddingTop": "4px"} });\n'
                'const sx_954f5c8b18_0 = { __proto__: null, "solid": { __proto__: '
                'null, "1": stylex.props(sx_954f5c8b18.a0_0).className, "2": '
                'stylex.props(sx_954f5c8b18.a0_1).className }, "soft": { __proto__: '
                'null, "1": stylex.props(sx_954f5c8b18.a0_2).className, "2": '
                "stylex.props(sx_954f5c8b18.a0_3).className } };\n"
                "const sx_954f5c8b18_0d = stylex.props(sx_954f5c8b18.a0).className;"
            ),
            lookups=("(sx_954f5c8b18_0[<kind>]?.[<size>] ?? sx_954f5c8b18_0d)",),
            imports=(RUBY,),
            vars=(
                "<kind>",
                "<size>",
            ),
        ),
    ),
    "variant_bound_with_var_value": (
        {"styles": SIZED, "props": {"kind": S.kind}},
        emitted(
            declaration=(
                'const sx_7cb0d9b7b2 = stylex.create({ a0_0: {"width": "var(--v0)"}, '
                'a0_1: {"width": "1px"} });\n'
                'const sx_7cb0d9b7b2_0 = { __proto__: null, "a": '
                'stylex.props(sx_7cb0d9b7b2.a0_0).className, "b": '
                "stylex.props(sx_7cb0d9b7b2.a0_1).className };"
            ),
            lookups=('(sx_7cb0d9b7b2_0[<kind>] ?? "")',),
            variables=('"--v0": (<width>) ?? "initial"',),
            vars=(
                "<width>",
                "<kind>",
            ),
        ),
    ),
    "whole_var": (
        {"styles": CARD, "style": S.styles},
        emitted(
            declaration=(
                'const sx_1026d57c33 = stylex.create({ s: {"paddingTop": '
                '"var(--space-3)", "paddingRight": "var(--space-3)", '
                '"paddingBottom": "var(--space-3)", "paddingLeft": '
                '"var(--space-3)", "borderTopLeftRadius": "var(--radius-4)", '
                '"borderTopRightRadius": "var(--radius-4)", '
                '"borderBottomRightRadius": "var(--radius-4)", '
                '"borderBottomLeftRadius": "var(--radius-4)", "boxShadow": '
                '"var(--shadow-2)"} });\n'
                "const sx_1026d57c33_c = "
                "stylex.props(sx_1026d57c33.s).className;"
            ),
            classes="sx_1026d57c33_c",
            imports=(
                "$/reflex-ui/tokens/radius.stylex.js",
                "$/reflex-ui/tokens/shadow.stylex.js",
                "$/reflex-ui/tokens/space.stylex.js",
            ),
            inline="<styles>",
            vars=("<styles>",),
        ),
    ),
    "whole_var_alone": (
        {"styles": NO_STYLES, "style": S.styles},
        emitted(
            inline="<styles>",
            vars=("<styles>",),
        ),
    ),
    "whole_var_after_styles": (
        {"styles": NO_STYLES, "style": [{"width": S.width}, S.styles]},
        emitted(
            declaration=(
                'const sx_67b044120d = stylex.create({ s: {"width": "var(--v0)"} });\n'
                "const sx_67b044120d_c = stylex.props(sx_67b044120d.s).className;"
            ),
            classes="sx_67b044120d_c",
            variables=('"--v0": (<width>) ?? "initial"',),
            inline="<styles>",
            vars=(
                "<width>",
                "<styles>",
            ),
        ),
    ),
}


@pytest.mark.parametrize("case", CASES)
def test_emit_writes_the_source_of_each_kind_of_style(case: str):
    arguments, expected = CASES[case]
    assert comparable(emit(merge("rx.ui.card", **arguments))) == expected


def test_emit_names_a_declaration_after_its_content():
    """Equal styles share a declaration; different ones never share a name."""

    def classes(style: dict[str, Any], name: str = "rx.ui.box") -> str | None:
        return emit(merge(name, NO_STYLES, style=style)).classes

    top = {"top": "4px"}
    assert classes(top) == classes(top, "rx.ui.flex") == "sx_d0020eea95_c"
    assert len({classes(top), classes({"top": "5px"}), classes({"top": 4})}) == 3
    # The declaration of a bound prop does not depend on the Var it is bound to.
    assert (
        emit(merge("rx.ui.button", BUTTON, {"tone": S.kind})).declaration
        == emit(merge("rx.ui.button", BUTTON, {"tone": S.size})).declaration
    )


def test_inline_keeps_literals():
    style = {"top": "4px", "z_index": 2, "opacity": 0.5}
    assert inline(merge("rx.ui.box", CARD, style=style), "rx.ui.box") == {
        "paddingTop": "var(--space-3)",
        "paddingRight": "var(--space-3)",
        "paddingBottom": "var(--space-3)",
        "paddingLeft": "var(--space-3)",
        "borderTopLeftRadius": "var(--radius-4)",
        "borderTopRightRadius": "var(--radius-4)",
        "borderBottomRightRadius": "var(--radius-4)",
        "borderBottomLeftRadius": "var(--radius-4)",
        "boxShadow": "var(--shadow-2)",
        "top": "4px",
        "zIndex": 2,
        "opacity": 0.5,
    }
    assert inline(merge("rx.ui.box", NO_STYLES), "rx.ui.box") == {}


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            {"styles": NO_STYLES, "style": {"color": "red", "_hover": {"color": "x"}}},
            (
                'rx.ui.box: the style "color" has conditions ("default", ":hover"), '
                "which a component rendered from state cannot apply: its code is "
                "evaluated in the browser and never reaches the StyleX compiler. Use an "
                "unconditional value there, or render the component in a page and show "
                "it with rx.cond."
            ),
        ),
        (
            {"styles": NO_STYLES, "style": {"color": S.width}},
            (
                'rx.ui.box: the style "color" is bound to state, which a component '
                "rendered from state cannot apply: its code is evaluated in the browser "
                "and never reaches the StyleX compiler. Use a literal value there, or "
                "render the component in a page and show it with rx.cond."
            ),
        ),
        (
            {"styles": NO_STYLES, "style": S.styles},
            (
                "rx.ui.box: the style is a Var, which a component rendered from state "
                "cannot apply: its code is evaluated in the browser and never reaches "
                "the StyleX compiler. Use a dict of literal values there, or render the "
                "component in a page and show it with rx.cond."
            ),
        ),
        (
            {"styles": BUTTON, "props": {"kind": S.kind, "size": S.size}},
            (
                'rx.ui.box: the props "kind", "size" select a style and are bound to '
                "state, which a component rendered from state cannot apply: its code is "
                "evaluated in the browser and never reaches the StyleX compiler. Give "
                "them literal values there, or render the component in a page and show "
                "it with rx.cond."
            ),
        ),
    ],
)
def test_inline_rejects_what_an_inline_style_cannot_hold(
    arguments: dict[str, Any], message: str
):
    with pytest.raises(StyleError) as raised:
        inline(merge("rx.ui.box", **arguments), "rx.ui.box")
    assert str(raised.value) == message
