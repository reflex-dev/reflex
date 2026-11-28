"""Tests for lowering the styles a user writes into what StyleX compiles."""

from typing import Any

import pytest
from reflex_base.breakpoints import breakpoints_values, set_breakpoints
from reflex_base.constants.colors import Color
from reflex_base.vars.base import LiteralVar, Var
from reflex_components_ui import tokens
from reflex_components_ui._radix_tokens import VAR_GROUPS
from reflex_components_ui.style import _css_props
from reflex_components_ui.style.lower import (
    _BORDERS,
    _EXPANSIONS,
    _LAYOUT,
    _REFLEX_KEYS,
    _REPLACES,
    _UNSUPPORTED,
    LAYOUT_PROPS,
    VAR_MODULES,
    Lowered,
    StyleError,
    apply_layer,
    finish,
    keyframes,
    lower,
    lower_layer,
)

import reflex as rx

RUBY = "$/reflex-ui/colors/ruby.stylex.js"
GRAY = "$/reflex-ui/tokens/gray.stylex.js"
ACCENT = "$/reflex-ui/tokens/accent.stylex.js"
SPACE = "$/reflex-ui/tokens/space.stylex.js"
XS = "@media screen and (min-width: 30em)"
SM = "@media screen and (min-width: 48em)"
MD = "@media screen and (min-width: 62em)"
LG = "@media screen and (min-width: 80em)"
XL = "@media screen and (min-width: 96em)"
# A responsive prop is on the breakpoints of Radix Themes instead.
PROP_XS = "@media (min-width: 520px)"
PROP_SM = "@media (min-width: 768px)"
PROP_MD = "@media (min-width: 1024px)"
PROP_LG = "@media (min-width: 1280px)"


class StyleState(rx.State):
    """State whose fields are bound to styles."""

    width: rx.Field[int] = rx.field(320)
    scale: rx.Field[str] = rx.field("ruby")
    style: rx.Field[dict[str, str]] = rx.field({})


WIDTH = StyleState.width
SCALE = StyleState.scale


def test_generated_tables_cover_what_lowering_names():
    """Every property lowering expands to, replaces or sets is a known one."""
    known = set(_css_props.CSS_PROPS.values())
    named = {
        *_EXPANSIONS,
        *(prop for longhands, _ in _EXPANSIONS.values() for prop in longhands),
        *_REPLACES,
        *(prop for replaced in _REPLACES.values() for prop in replaced),
        *(prop for targets in _REFLEX_KEYS.values() for prop in targets),
        *_BORDERS,
        *_UNSUPPORTED,
        *(
            f"{side}{part}"
            for sides in _BORDERS.values()
            for side in sides
            for part in ("Width", "Style", "Color")
        ),
        *(prop for _, targets, _ in _LAYOUT.values() for prop in targets),
    }
    assert named - known == set()
    assert {key: _css_props.CSS_PROPS.get(key) for key, _, _ in _LAYOUT.values()} == {
        "padding": "padding",
        "padding_x": None,
        "padding_y": None,
        "padding_top": "paddingTop",
        "padding_right": "paddingRight",
        "padding_bottom": "paddingBottom",
        "padding_left": "paddingLeft",
        "margin": "margin",
        "margin_x": None,
        "margin_y": None,
        "margin_top": "marginTop",
        "margin_right": "marginRight",
        "margin_bottom": "marginBottom",
        "margin_left": "marginLeft",
        "gap": "gap",
        "column_gap": "columnGap",
        "row_gap": "rowGap",
        "grid_template_columns": "gridTemplateColumns",
        "grid_template_rows": "gridTemplateRows",
        "flex_direction": "flexDirection",
        "flex_wrap": "flexWrap",
        "align_items": "alignItems",
        "justify_content": "justifyContent",
        "grid_auto_flow": "gridAutoFlow",
    }


def test_generated_table_spells_properties_as_users_do():
    """A sample of the generated keys, vendor prefixes included."""
    sample = (
        "background_color",
        "border_top_left_radius",
        "webkit_font_smoothing",
        "moz_osx_font_smoothing",
        "z_index",
        "float",
        "theme",
    )
    assert {key: _css_props.CSS_PROPS.get(key) for key in sample} == {
        "background_color": "backgroundColor",
        "border_top_left_radius": "borderTopLeftRadius",
        "webkit_font_smoothing": "WebkitFontSmoothing",
        "moz_osx_font_smoothing": "MozOsxFontSmoothing",
        "z_index": "zIndex",
        "float": "float",
        "theme": None,
    }
    assert len(_css_props.CSS_PROPS) == 521
    assert _css_props.StyleProps is dict


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        ({}, {}),
        (None, {}),
        (
            {"display": "flex", "z_index": 3, "line_height": 1.5, "color": "red"},
            {"display": "flex", "zIndex": 3, "lineHeight": 1.5, "color": "red"},
        ),
        (
            {"backgroundColor": "red", "font-size": "2em", "--card-gap": "4px"},
            {"backgroundColor": "red", "fontSize": "2em", "--card-gap": "4px"},
        ),
        (
            {"_webkit_font_smoothing": "antialiased", "webkit_appearance": "none"},
            {"WebkitFontSmoothing": "antialiased", "WebkitAppearance": "none"},
        ),
        (
            {"width": LiteralVar.create("10px"), "order": LiteralVar.create(2)},
            {"width": "10px", "order": 2},
        ),
        ({"color": "red", "width": None}, {"color": "red"}),
    ],
)
def test_literal_values(style: Any, expected: dict[str, Any]):
    """A literal value stays a literal under the camelCase name of its property.

    Args:
        style: The style as written.
        expected: The lowered properties.
    """
    assert lower("rx.ui.card", style) == Lowered(expected)


def test_literal_values_keep_their_order():
    """The properties come out in the order they were written."""
    lowered = lower("rx.ui.card", {"width": "1px", "color": "red", "top": 0})
    assert list(lowered.style.items()) == [
        ("width", "1px"),
        ("color", "red"),
        ("top", 0),
    ]
    assert (lowered.imports, lowered.inline) == ((), None)


def test_state_var_values():
    """A value bound to state is kept as its Var, wherever it is written."""
    concatenated = LiteralVar.create(f"{WIDTH}px")
    assert lower(
        "rx.ui.card",
        {
            "width": WIDTH,
            "height": f"{WIDTH}px",
            "min_width": [WIDTH, "50%"],
            "_hover": {"max_width": WIDTH},
            "padding": WIDTH,
            "padding_x": WIDTH,
        },
    ) == Lowered({
        "width": WIDTH,
        "height": concatenated,
        "minWidth": {"default": WIDTH, XS: "50%"},
        "maxWidth": {":hover": WIDTH},
        "padding": WIDTH,
        "paddingLeft": WIDTH,
        "paddingRight": WIDTH,
    })


def test_whole_dict_var_becomes_the_inline_style():
    """A Var holding a dict of styles is not lowered, only carried."""
    lowered = lower("rx.ui.card", StyleState.style)
    assert lowered == Lowered({}, (), StyleState.style)
    assert lowered.style == {}
    assert lowered.inline is not None
    assert lowered.inline.equals(StyleState.style)
    assert lower("rx.ui.card", StyleState.style, {"p": "2"}) == Lowered(
        {
            "paddingTop": "var(--space-2)",
            "paddingRight": "var(--space-2)",
            "paddingBottom": "var(--space-2)",
            "paddingLeft": "var(--space-2)",
        },
        (SPACE,),
        StyleState.style,
    )


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        (
            {"color": "black", "_hover": {"color": "blue"}},
            {"color": {"default": "black", ":hover": "blue"}},
        ),
        (
            {"_hover": {"color": "blue"}, "color": "black"},
            {"color": {"default": "black", ":hover": "blue"}},
        ),
        (
            {":focus-visible": {"outline_style": "solid"}},
            {"outlineStyle": {":focus-visible": "solid"}},
        ),
        (
            {"_focus_visible": {"color": "red"}, "_focusWithin": {"color": "blue"}},
            {"color": {":focus-visible": "red", ":focus-within": "blue"}},
        ),
        (
            {"_before": {"content": '""'}, "_placeholder": {"color": "gray"}},
            {"content": {"::before": '""'}, "color": {"::placeholder": "gray"}},
        ),
        (
            {"::-webkit-scrollbar": {"display": "none"}, "&:hover": {"top": 0}},
            {"display": {"::-webkit-scrollbar": "none"}, "top": {":hover": 0}},
        ),
        (
            {
                "[data-open]": {"opacity": 1},
                "&[data-disabled]": {"opacity": 0.5},
                ":not(:first-child)": {"opacity": 0},
                ":nth-child(2n + 1)": {"opacity": 0.2},
            },
            {
                "opacity": {
                    "[data-open]": 1,
                    "[data-disabled]": 0.5,
                    ":not(:first-child)": 0,
                    ":nth-child(2n + 1)": 0.2,
                }
            },
        ),
        (
            {
                "@media (min-width: 768px)": {"color": "red"},
                "@container (min-width: 20em)": {"color": "blue"},
                "@supports (display: grid)": {"color": "green"},
                "@starting-style": {"color": "pink"},
            },
            {
                "color": {
                    "@media (min-width: 768px)": "red",
                    "@container (min-width: 20em)": "blue",
                    "@supports (display: grid)": "green",
                    "@starting-style": "pink",
                }
            },
        ),
        (
            {"_hover": {"color": "red", "_disabled": {"color": "gray"}}},
            {"color": {":hover": {"default": "red", ":disabled": "gray"}}},
        ),
        (
            {"_hover": {"_disabled": {"color": "gray"}, "color": "red"}},
            {"color": {":hover": {"default": "red", ":disabled": "gray"}}},
        ),
        (
            {"color": {"default": "black", ":hover": "blue", "_active": "red"}},
            {"color": {"default": "black", ":hover": "blue", ":active": "red"}},
        ),
        (
            {"color": {":hover": {"default": "blue", "@media print": "black"}}},
            {"color": {":hover": {"default": "blue", "@media print": "black"}}},
        ),
        (
            {"color": None, "_hover": {"color": "blue"}},
            {"color": {"default": None, ":hover": "blue"}},
        ),
        (
            {"_hover": {"margin": "0 auto"}},
            {
                "marginTop": {":hover": "0"},
                "marginRight": {":hover": "auto"},
                "marginBottom": {":hover": "0"},
                "marginLeft": {":hover": "auto"},
            },
        ),
    ],
)
def test_condition_blocks(style: Any, expected: dict[str, Any]):
    """A block of styles under a condition becomes per-property conditions.

    Args:
        style: The style as written.
        expected: The lowered properties.
    """
    assert lower("rx.ui.card", style) == Lowered(expected)


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        ({"width": ["100%"]}, {"width": "100%"}),
        ({"width": ["100%", "50%"]}, {"width": {"default": "100%", XS: "50%"}}),
        (
            {"width": ("1px", "2px", "3px", "4px", "5px", "6px")},
            {
                "width": {
                    "default": "1px",
                    XS: "2px",
                    SM: "3px",
                    MD: "4px",
                    LG: "5px",
                    XL: "6px",
                }
            },
        ),
        ({"width": [None, None, "50%"]}, {"width": {SM: "50%"}}),
        (
            {"width": rx.breakpoints(initial="100%", sm="50%", xl="25%")},
            {"width": {"default": "100%", SM: "50%", XL: "25%"}},
        ),
        ({"width": rx.breakpoints(md="50%")}, {"width": {MD: "50%"}}),
        (
            {"width": rx.breakpoints(custom={"500px": "50%", "xs": "75%"})},
            {
                "width": {
                    "@media screen and (min-width: 500px)": "50%",
                    XS: "75%",
                }
            },
        ),
        (
            {"width": {"initial": "100%", "lg": "50%"}},
            {"width": {"default": "100%", LG: "50%"}},
        ),
        (
            {"_hover": {"width": ["100%", "50%"]}},
            {"width": {":hover": {"default": "100%", XS: "50%"}}},
        ),
        (
            {"width": ["100%", {"default": "50%", ":hover": "60%"}]},
            {"width": {"default": "100%", XS: {"default": "50%", ":hover": "60%"}}},
        ),
        (
            {"padding_x": ["1em", "2em"]},
            {
                "paddingLeft": {"default": "1em", XS: "2em"},
                "paddingRight": {"default": "1em", XS: "2em"},
            },
        ),
        (
            {"gap": rx.breakpoints(initial="1em", sm="1em 2em")},
            {
                "rowGap": {"default": "1em", SM: "1em"},
                "columnGap": {"default": "1em", SM: "2em"},
            },
        ),
    ],
)
def test_responsive_values(style: Any, expected: dict[str, Any]):
    """A responsive value becomes media queries on the five breakpoints.

    Args:
        style: The style as written.
        expected: The lowered properties.
    """
    assert lower("rx.ui.card", style) == Lowered(expected)


def test_responsive_values_follow_the_configured_breakpoints():
    """The media queries are read from the breakpoints of the app."""
    original = tuple(breakpoints_values)
    set_breakpoints(("10px", "20px", "30px", "40px", "50px"))
    try:
        lowered = lower(
            "rx.ui.card", {"width": ["1px", "2px"], "top": rx.breakpoints(xl="0")}
        )
    finally:
        set_breakpoints(original)  # pyright: ignore [reportArgumentType]
    assert lowered == Lowered({
        "width": {"default": "1px", "@media screen and (min-width: 10px)": "2px"},
        "top": {"@media screen and (min-width: 50px)": "0"},
    })


@pytest.mark.parametrize(
    ("style", "expected", "imports"),
    [
        ({"color": rx.color("ruby", 9)}, {"color": "var(--ruby-9)"}, (RUBY,)),
        ({"color": rx.color("ruby", 3, True)}, {"color": "var(--ruby-a3)"}, (RUBY,)),
        (
            {"color": LiteralVar.create(rx.color("gray", 11))},
            {"color": "var(--gray-11)"},
            (GRAY,),
        ),
        ({"color": rx.color("accent", 9)}, {"color": "var(--accent-9)"}, (ACCENT,)),
        (
            {"outline": f"1px solid {rx.color('ruby', 6)}", "color": "var(--gray-a11)"},
            {"outline": "1px solid var(--ruby-6)", "color": "var(--gray-a11)"},
            (RUBY, GRAY),
        ),
        (
            {
                "color": {
                    "default": rx.color("gray", 12),
                    ":hover": [rx.color("ruby", 9), rx.color("ruby", 10)],
                }
            },
            {
                "color": {
                    "default": "var(--gray-12)",
                    ":hover": {"default": "var(--ruby-9)", XS: "var(--ruby-10)"},
                }
            },
            (RUBY, GRAY),
        ),
        (
            {"border_color": rx.color("ruby", 6)},
            {
                "borderTopColor": "var(--ruby-6)",
                "borderRightColor": "var(--ruby-6)",
                "borderBottomColor": "var(--ruby-6)",
                "borderLeftColor": "var(--ruby-6)",
            },
            (RUBY,),
        ),
        (
            {"color": "var(--my-color)", "width": "var(--space-4)"},
            {"color": "var(--my-color)", "width": "var(--space-4)"},
            (SPACE,),
        ),
        (
            {"color": rx.color(SCALE, 9)},
            {"color": LiteralVar.create(Color(SCALE, 9))},
            (),
        ),
    ],
)
def test_colors_and_tokens(
    style: Any, expected: dict[str, Any], imports: tuple[str, ...]
):
    """A color becomes its custom property and names the module of its scale.

    Args:
        style: The style as written.
        expected: The lowered properties.
        imports: The modules the style needs.
    """
    lowered = lower("rx.ui.card", style)
    assert lowered == Lowered(expected, imports)
    assert lowered.imports == imports


def test_var_modules_name_the_module_of_every_custom_property():
    """Each custom property Radix defines is found by its whole name."""
    assert VAR_MODULES["--ruby-9"] == RUBY
    assert VAR_MODULES["--gray-9"] == GRAY
    assert {
        name: f"$/reflex-ui/{module}"
        for module, names in VAR_GROUPS.values()
        for name in names
    } == VAR_MODULES
    assert len(VAR_MODULES) == 1070
    assert lower(
        "rx.ui.card",
        {
            "width": "calc(2 * var(--space-4))",
            "flex_grow": "var(--scaling)",
            "font_size": "var(--font-size-2, 14px)",
            "line_height": "var( --line-height-2 )",
            # Not custom properties of Radix Themes: an app may define them,
            # and they import nothing, whatever word they start with.
            "color": "var(--mine-1)",
            "background_color": "var(--color-mine)",
            "border_top_color": "var(--gray-13)",
            "font_family": "var(--code-font)",
        },
    ).imports == (
        "$/reflex-ui/tokens/scaling.stylex.js",
        "$/reflex-ui/tokens/space.stylex.js",
        "$/reflex-ui/tokens/typography.stylex.js",
    )


def _sides(prefix: str, suffix: str, *values: Any) -> dict[str, Any]:
    """Build the four longhands of a box shorthand.

    Args:
        prefix: What comes before the side.
        suffix: What comes after it.
        values: The top, right, bottom and left values.

    Returns:
        The lowered properties.
    """
    sides = ("Top", "Right", "Bottom", "Left")
    return {
        f"{prefix}{side}{suffix}": value
        for side, value in zip(sides, values, strict=True)
    }


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        ({"margin": "0 auto"}, _sides("margin", "", "0", "auto", "0", "auto")),
        ({"margin": "1em"}, _sides("margin", "", "1em", "1em", "1em", "1em")),
        ({"margin": 4}, _sides("margin", "", 4, 4, 4, 4)),
        ({"padding": "1px 2px 3px"}, _sides("padding", "", "1px", "2px", "3px", "2px")),
        (
            {"padding": "1px 2px 3px 4px"},
            _sides("padding", "", "1px", "2px", "3px", "4px"),
        ),
        (
            {"padding": "calc(1px + 2px)  max(1em, 4px)"},
            {"padding": "calc(1px + 2px)  max(1em, 4px)"},
        ),
        (
            {"padding": "calc(1px + 2px) min(1em 4px)"},
            _sides(
                "padding",
                "",
                "calc(1px + 2px)",
                "min(1em 4px)",
                "calc(1px + 2px)",
                "min(1em 4px)",
            ),
        ),
        ({"padding": "var(--card-padding)"}, {"padding": "var(--card-padding)"}),
        ({"padding": "1px 2px 3px 4px 5px"}, {"padding": "1px 2px 3px 4px 5px"}),
        ({"margin": "0 !important"}, {"margin": "0 !important"}),
        (
            {"inset": "0 auto"},
            {"top": "0", "right": "auto", "bottom": "0", "left": "auto"},
        ),
        (
            {"border_width": "1px 2px"},
            _sides("border", "Width", "1px", "2px", "1px", "2px"),
        ),
        (
            {"border_style": "solid"},
            _sides("border", "Style", "solid", "solid", "solid", "solid"),
        ),
        (
            {"border_color": "rgb(0 0 0) red"},
            _sides("border", "Color", "rgb(0 0 0)", "red", "rgb(0 0 0)", "red"),
        ),
        (
            {"border_radius": "4px 8px"},
            {
                "borderTopLeftRadius": "4px",
                "borderTopRightRadius": "8px",
                "borderBottomRightRadius": "4px",
                "borderBottomLeftRadius": "8px",
            },
        ),
        ({"border_radius": "50% / 10%"}, {"borderRadius": "50% / 10%"}),
        ({"gap": "1em"}, {"rowGap": "1em", "columnGap": "1em"}),
        ({"gap": "1em 2em"}, {"rowGap": "1em", "columnGap": "2em"}),
        ({"overflow": "hidden auto"}, {"overflowX": "hidden", "overflowY": "auto"}),
        (
            {"margin_inline": "1em 2em", "padding_block": "3em"},
            {
                "marginInlineStart": "1em",
                "marginInlineEnd": "2em",
                "paddingBlockStart": "3em",
                "paddingBlockEnd": "3em",
            },
        ),
        (
            {"padding_x": "1em 2em", "margin_y": 0},
            {
                "paddingLeft": "1em 2em",
                "paddingRight": "1em 2em",
                "marginTop": 0,
                "marginBottom": 0,
            },
        ),
        (
            {"bg": "red", "bg_color": "blue", "paddingX": "1px", "margin-x": "2px"},
            {
                "backgroundColor": "blue",
                "backgroundImage": "none",
                "paddingLeft": "1px",
                "paddingRight": "1px",
                "marginLeft": "2px",
                "marginRight": "2px",
            },
        ),
        (
            {"margin_top": "1em", "margin": "0"},
            _sides("margin", "", "0", "0", "0", "0"),
        ),
        (
            {"margin": "0", "margin_top": "1em"},
            _sides("margin", "", "1em", "0", "0", "0"),
        ),
        (
            {"outline": "1px solid red", "transition": "all 0.2s", "flex": "1 1 0"},
            {"outline": "1px solid red", "transition": "all 0.2s", "flex": "1 1 0"},
        ),
    ],
)
def test_shorthands(style: Any, expected: dict[str, Any]):
    """A shorthand whose values can be told apart is expanded to longhands.

    Args:
        style: The style as written.
        expected: The lowered properties.
    """
    assert lower("rx.ui.card", style) == Lowered(expected)


def _border(sides: tuple[str, ...], width: Any, style: Any, color: Any) -> dict:
    """Build the longhands of a border shorthand.

    Args:
        sides: The sides it sets, such as ``borderTop``.
        width: The width of each side.
        style: The style of each side.
        color: The color of each side.

    Returns:
        The lowered properties.
    """
    parts = (("Width", width), ("Style", style), ("Color", color))
    return {f"{side}{part}": value for side in sides for part, value in parts}


ALL_SIDES = ("borderTop", "borderRight", "borderBottom", "borderLeft")


@pytest.mark.parametrize(
    ("style", "expected", "imports"),
    [
        ({"border": "1px solid red"}, _border(ALL_SIDES, "1px", "solid", "red"), ()),
        ({"border": "red solid 1px"}, _border(ALL_SIDES, "1px", "solid", "red"), ()),
        (
            {"border": f"1px solid {rx.color('gray', 6)}"},
            _border(ALL_SIDES, "1px", "solid", "var(--gray-6)"),
            (GRAY,),
        ),
        (
            {"border": "calc(1px + 1px) dashed rgb(0 0 0 / 50%)"},
            _border(ALL_SIDES, "calc(1px + 1px)", "dashed", "rgb(0 0 0 / 50%)"),
            (),
        ),
        ({"border": "none"}, _border(ALL_SIDES, "medium", "none", "currentcolor"), ()),
        ({"border": 0}, _border(ALL_SIDES, 0, "none", "currentcolor"), ()),
        ({"border": "thin"}, _border(ALL_SIDES, "thin", "none", "currentcolor"), ()),
        (
            {"border": rx.color("ruby", 6)},
            _border(ALL_SIDES, "medium", "none", "var(--ruby-6)"),
            (RUBY,),
        ),
        (
            {"border_top": "2px dotted", "borderLeft": ".5em solid blue"},
            {
                **_border(("borderTop",), "2px", "dotted", "currentcolor"),
                **_border(("borderLeft",), ".5em", "solid", "blue"),
            },
            (),
        ),
        (
            {"border_right": "1px solid", "border_bottom": "1px solid"},
            _border(("borderRight", "borderBottom"), "1px", "solid", "currentcolor"),
            (),
        ),
        (
            {"border_block": "1px solid", "border_inline": "2px solid"},
            {
                **_border(
                    ("borderTop", "borderBottom"), "1px", "solid", "currentcolor"
                ),
                **_border(
                    ("borderInlineStart", "borderInlineEnd"),
                    "2px",
                    "solid",
                    "currentcolor",
                ),
            },
            (),
        ),
        (
            {
                "border_block_start": "1px solid",
                "border_block_end": "2px solid",
                "border_inline_start": "3px solid",
                "border_inline_end": "4px solid",
            },
            {
                **_border(("borderTop",), "1px", "solid", "currentcolor"),
                **_border(("borderBottom",), "2px", "solid", "currentcolor"),
                **_border(("borderInlineStart",), "3px", "solid", "currentcolor"),
                **_border(("borderInlineEnd",), "4px", "solid", "currentcolor"),
            },
            (),
        ),
        (
            {"border": "1px solid red", "border_top": None},
            {
                **_border(ALL_SIDES[1:], "1px", "solid", "red"),
            },
            (),
        ),
        (
            {"border": "1px solid red", "_hover": {"border_color": "blue"}},
            {
                **_border(
                    ALL_SIDES, "1px", "solid", {"default": "red", ":hover": "blue"}
                ),
            },
            (),
        ),
        (
            {"background": "red", "bg": "blue"},
            {"backgroundColor": "blue", "backgroundImage": "none"},
            (),
        ),
        (
            {"bg": rx.color("ruby", 3), "_hover": {"background": "none"}},
            {
                "backgroundColor": {
                    "default": "var(--ruby-3)",
                    ":hover": "transparent",
                },
                "backgroundImage": {"default": "none", ":hover": "none"},
            },
            (RUBY,),
        ),
        (
            {"background": "var(--surface)"},
            {"backgroundColor": "var(--surface)", "backgroundImage": "none"},
            (),
        ),
        (
            {"background": "linear-gradient(90deg, red 0%, blue 100%)"},
            {
                "backgroundColor": "transparent",
                "backgroundImage": "linear-gradient(90deg, red 0%, blue 100%)",
            },
            (),
        ),
        (
            {"background": ["URL(a.png)", "repeating-conic-gradient(red, blue)"]},
            {
                "backgroundColor": {"default": "transparent", XS: "transparent"},
                "backgroundImage": {
                    "default": "URL(a.png)",
                    XS: "repeating-conic-gradient(red, blue)",
                },
            },
            (),
        ),
        ({"background": None, "color": "red"}, {"color": "red"}, ()),
    ],
)
def test_shorthands_stylex_does_not_compile(
    style: Any, expected: dict[str, Any], imports: tuple[str, ...]
):
    """The border and background shorthands are split, having no other form.

    Args:
        style: The style as written.
        expected: The lowered properties.
        imports: The modules the style needs.
    """
    assert lower("rx.ui.card", style) == Lowered(expected, imports)


@pytest.mark.parametrize(
    ("layout", "expected"),
    [
        ({"p": "4"}, _sides("padding", "", *["var(--space-4)"] * 4)),
        (
            {"p": "0", "m": "-0"},
            {**_sides("padding", "", *["0"] * 4), **_sides("margin", "", *["0"] * 4)},
        ),
        ({"m": "-2"}, _sides("margin", "", *["calc(-1 * var(--space-2))"] * 4)),
        (
            {"m": "auto", "p": "10px", "pt": 3},
            {
                **_sides("margin", "", *["auto"] * 4),
                **_sides("padding", "", 3, "10px", "10px", "10px"),
            },
        ),
        (
            {"px": "1", "py": "2", "mx": "3", "my": "4"},
            {
                "paddingLeft": "var(--space-1)",
                "paddingRight": "var(--space-1)",
                "paddingTop": "var(--space-2)",
                "paddingBottom": "var(--space-2)",
                "marginLeft": "var(--space-3)",
                "marginRight": "var(--space-3)",
                "marginTop": "var(--space-4)",
                "marginBottom": "var(--space-4)",
            },
        ),
        (
            {"pt": "1", "pr": "2", "pb": "3", "pl": "4"},
            _sides("padding", "", *[f"var(--space-{step})" for step in "1234"]),
        ),
        (
            {"mt": "1", "mr": "2", "mb": "3", "ml": "4"},
            _sides("margin", "", *[f"var(--space-{step})" for step in "1234"]),
        ),
        ({"gap": "3"}, {"rowGap": "var(--space-3)", "columnGap": "var(--space-3)"}),
        ({"spacing": "9"}, {"rowGap": "var(--space-9)", "columnGap": "var(--space-9)"}),
        ({"gap": "10"}, {"rowGap": "10", "columnGap": "10"}),
        (
            {"gap_x": "1", "gap_y": "2"},
            {"columnGap": "var(--space-1)", "rowGap": "var(--space-2)"},
        ),
        (
            {"gap": ["1", "2"]},
            {
                "rowGap": {"default": "var(--space-1)", PROP_XS: "var(--space-2)"},
                "columnGap": {"default": "var(--space-1)", PROP_XS: "var(--space-2)"},
            },
        ),
        (
            {"p": rx.breakpoints(initial="1", md="4")},
            _sides(
                "padding",
                "",
                *[{"default": "var(--space-1)", PROP_MD: "var(--space-4)"}] * 4,
            ),
        ),
        (
            {"columns": "3", "rows": "2"},
            {
                "gridTemplateColumns": "repeat(3, minmax(0, 1fr))",
                "gridTemplateRows": "repeat(2, minmax(0, 1fr))",
            },
        ),
        (
            {"columns": {"initial": "1", "sm": "repeat(2, 10em)"}},
            {
                "gridTemplateColumns": {
                    "default": "repeat(1, minmax(0, 1fr))",
                    PROP_SM: "repeat(2, 10em)",
                }
            },
        ),
        (
            {"direction": "column", "wrap": "wrap", "flow": "row-dense"},
            {
                "flexDirection": "column",
                "flexWrap": "wrap",
                "gridAutoFlow": "row dense",
            },
        ),
        (
            {"direction": ["column", "row"], "align": "start", "justify": "between"},
            {
                "flexDirection": {"default": "column", PROP_XS: "row"},
                "alignItems": "flex-start",
                "justifyContent": "space-between",
            },
        ),
        (
            {"align": ["end", "center"], "justify": {"initial": "end", "lg": "start"}},
            {
                "alignItems": {"default": "flex-end", PROP_XS: "center"},
                "justifyContent": {"default": "flex-end", PROP_LG: "flex-start"},
            },
        ),
        ({"direction": SCALE}, {"flexDirection": SCALE}),
        (
            {"gap": LiteralVar.create("2"), "p": None},
            {"rowGap": "var(--space-2)", "columnGap": "var(--space-2)"},
        ),
    ],
)
def test_layout_props(layout: dict[str, Any], expected: dict[str, Any]):
    """A layout prop becomes the styles it stands for, at every breakpoint.

    Args:
        layout: The layout props.
        expected: The lowered properties.
    """
    lowered = lower("rx.ui.flex", None, layout)
    assert lowered.style == expected
    # Only a step of the space scale needs a module.
    assert lowered.imports == ((SPACE,) if "var(--space-" in repr(expected) else ())


def test_layout_props_are_merged_under_the_style():
    """The style of the element wins over its layout props, by property."""
    assert lower(
        "rx.ui.flex",
        {"padding_top": "1px", "_hover": {"row_gap": "0"}, "margin": WIDTH},
        {"p": "2", "gap": "3", "mt": "1"},
    ) == Lowered(
        {
            "paddingTop": "1px",
            "paddingRight": "var(--space-2)",
            "paddingBottom": "var(--space-2)",
            "paddingLeft": "var(--space-2)",
            "rowGap": {"default": "var(--space-3)", ":hover": "0"},
            "columnGap": "var(--space-3)",
            "margin": WIDTH,
        },
        (SPACE,),
    )
    assert (
        frozenset({
            "p",
            "px",
            "py",
            "pt",
            "pr",
            "pb",
            "pl",
            "m",
            "mx",
            "my",
            "mt",
            "mr",
            "mb",
            "ml",
            "gap",
            "spacing",
            "gap_x",
            "gap_y",
            "spacing_x",
            "spacing_y",
            "columns",
            "rows",
            "direction",
            "wrap",
            "align",
            "justify",
            "flow",
        })
        == LAYOUT_PROPS
    )


@pytest.mark.parametrize(
    ("name", "style", "layout", "message"),
    [
        (
            "rx.ui.card",
            {"& > div": {"color": "red"}},
            None,
            (
                'rx.ui.card: style key "& > div" is a nested selector, which rx.ui '
                "styles do not support. Style the child component directly, or keep "
                "rx.card for this element."
            ),
        ),
        (
            "rx.ui.card",
            {"paddng": "1em"},
            None,
            'rx.ui.card: unknown CSS property "paddng". Did you mean "padding"?',
        ),
        (
            "rx.ui.stack",
            {"& :where(.rx-Stack)": {"width": "100%"}},
            None,
            (
                'rx.ui.stack: style key "& :where(.rx-Stack)" is a nested selector, '
                "which rx.ui styles do not support. Style the child component "
                "directly, or keep rx.stack for this element."
            ),
        ),
        (
            "rx.ui.card",
            {":hover > div": {"color": "red"}},
            None,
            (
                'rx.ui.card: style key ":hover > div" is a nested selector, which '
                "rx.ui styles do not support. Style the child component directly, "
                "or keep rx.card for this element."
            ),
        ),
        (
            "rx.ui.card",
            {"[data-open] span": {"color": "red"}},
            None,
            (
                'rx.ui.card: style key "[data-open] span" is a nested selector, '
                "which rx.ui styles do not support. Style the child component "
                "directly, or keep rx.card for this element."
            ),
        ),
        (
            "rx.ui.card",
            {".child": {"color": "red"}},
            None,
            (
                'rx.ui.card: style key ".child" is a nested selector, which rx.ui '
                "styles do not support. Style the child component directly, or keep "
                "rx.card for this element."
            ),
        ),
        (
            "rx.ui.card",
            {"_hover": {"&::after, &::before": {"color": "red"}}},
            None,
            (
                'rx.ui.card: style key "&::after, &::before" is a nested selector, '
                "which rx.ui styles do not support. Style the child component "
                "directly, or keep rx.card for this element."
            ),
        ),
        (
            "rx.ui.card",
            {"background_colour": "red"},
            None,
            (
                'rx.ui.card: unknown CSS property "background_colour". Did you mean '
                '"background_color"?'
            ),
        ),
        (
            "rx.ui.card",
            {"backgroundColr": "red"},
            None,
            (
                'rx.ui.card: unknown CSS property "backgroundColr". Did you mean '
                '"backgroundColor"?'
            ),
        ),
        (
            "rx.ui.card",
            {"font-sise": "red"},
            None,
            'rx.ui.card: unknown CSS property "font-sise". Did you mean "font_size"?',
        ),
        (
            "rx.ui.card",
            {"xyzzy": "red"},
            None,
            'rx.ui.card: unknown CSS property "xyzzy".',
        ),
        (
            "rx.ui.card",
            {"_hover": {"colr": "red"}},
            None,
            'rx.ui.card: unknown CSS property "colr". Did you mean "color"?',
        ),
        (
            "rx.ui.card",
            {"_hovr": {"color": "red"}},
            None,
            'rx.ui.card: unknown pseudo-class "_hovr". Did you mean "_hover"?',
        ),
        (
            "rx.ui.card",
            {"_zzzzzz": {"color": "red"}},
            None,
            'rx.ui.card: unknown pseudo-class "_zzzzzz".',
        ),
        (
            "rx.ui.card",
            {"@keyframes spin": {"color": "red"}},
            None,
            (
                'rx.ui.card: style key "@keyframes spin" is an at-rule that rx.ui '
                "styles do not support. Use @media, @container, @supports or "
                "@starting-style."
            ),
        ),
        (
            "rx.ui.card",
            {"_hover": StyleState.style},
            None,
            (
                'rx.ui.card: style key "_hover" is bound to state, but the styles '
                "under a condition are compiled ahead of time. Bind the values of "
                "its properties instead."
            ),
        ),
        (
            "rx.ui.card",
            {"_hover": "red"},
            None,
            (
                'rx.ui.card: style key "_hover" is a condition, so its value must be '
                "a dict of styles, not str."
            ),
        ),
        (
            "rx.ui.card",
            {"_hover": rx.breakpoints(sm={"color": "red"})},
            None,
            (
                'rx.ui.card: style key "_hover" is a condition, so its value must be '
                "a dict of styles, not Breakpoints."
            ),
        ),
        (
            "rx.ui.card",
            {"color": {"default": "red", "hover": "blue"}},
            None,
            (
                'rx.ui.card: style "color" is given a value under "hover", which is '
                'not a condition. Use "default", a pseudo-class such as ":hover", an '
                'at-rule such as "@media (min-width: 48em)" or the name of a '
                "breakpoint."
            ),
        ),
        (
            "rx.ui.card",
            {"color": {"default": "red", 3: "blue"}},
            None,
            (
                'rx.ui.card: style "color" is given a value under "3", which is '
                'not a condition. Use "default", a pseudo-class such as ":hover", an '
                'at-rule such as "@media (min-width: 48em)" or the name of a '
                "breakpoint."
            ),
        ),
        (
            "rx.ui.card",
            {"width": ["1px", "2px", "3px", "4px", "5px", "6px", "7px"]},
            None,
            (
                'rx.ui.card: style "width" has 7 responsive values, but there are '
                "only 6 breakpoints."
            ),
        ),
        (
            "rx.ui.card",
            {"visibility": True},
            None,
            (
                'rx.ui.card: style "visibility" cannot take a value of type bool. '
                "Use a string, a number, a Var, a responsive list or a dict of "
                "conditions."
            ),
        ),
        (
            "rx.ui.card",
            {"padding_x": [{"wat"}]},
            None,
            (
                'rx.ui.card: style "padding_x" cannot take a value of type set. Use '
                "a string, a number, a Var, a responsive list or a dict of "
                "conditions."
            ),
        ),
        (
            "rx.ui.card",
            {3: "red"},
            None,
            "rx.ui.card: a style key must be a string, not 3.",
        ),
        (
            "rx.ui.card",
            {"border": WIDTH},
            None,
            (
                'rx.ui.card: style "border" is bound to state, but rx.ui styles '
                "split this shorthand into longhands at compile time. Bind its "
                "width, style and color instead."
            ),
        ),
        (
            "rx.ui.card",
            {"border_top": "1px 2px"},
            None,
            (
                'rx.ui.card: style "border_top" has the value "1px 2px", which '
                "rx.ui styles cannot split into longhands. Set its width, style and "
                "color instead."
            ),
        ),
        (
            "rx.ui.card",
            {"border": "1px solid red !important"},
            None,
            (
                'rx.ui.card: style "border" has the value "1px solid red '
                '!important", which rx.ui styles cannot split into longhands. Set '
                "its width, style and color instead."
            ),
        ),
        (
            "rx.ui.card",
            {"bg": "url(a.png) center / cover"},
            None,
            (
                'rx.ui.card: style "bg" has the value "url(a.png) center / cover", '
                "which rx.ui styles cannot split into longhands. Set "
                "background_color, background_image and its other longhands instead."
            ),
        ),
        (
            "rx.ui.card",
            {"background": 3},
            None,
            (
                'rx.ui.card: style "background" has the value "3", which rx.ui '
                "styles cannot split into longhands. Set background_color, "
                "background_image and its other longhands instead."
            ),
        ),
        (
            "rx.ui.card",
            {"background": SCALE},
            None,
            (
                'rx.ui.card: style "background" is bound to state, but rx.ui styles '
                "split this shorthand into longhands at compile time. Bind "
                "background_color, background_image and its other longhands instead."
            ),
        ),
        (
            "rx.ui.card",
            {"animation": "spin 1s linear infinite"},
            None,
            (
                'rx.ui.card: style "animation" is a shorthand that rx.ui styles do '
                "not support. Set animation_name, animation_duration and its other "
                "longhands instead."
            ),
        ),
        (
            "rx.ui.card",
            {"all": "unset"},
            None,
            'rx.ui.card: unknown CSS property "all".',
        ),
        (
            "rx.ui.flex",
            None,
            {"gap": SCALE},
            (
                'rx.ui.flex: layout prop "gap" is bound to state, but its values are '
                'read at compile time. Bind the "gap" style instead, which takes any '
                "CSS value."
            ),
        ),
        (
            "rx.ui.flex",
            None,
            {"justify": ["start", SCALE]},
            (
                'rx.ui.flex: layout prop "justify" is bound to state, but its values '
                'are read at compile time. Bind the "justify_content" style instead, '
                "which takes any CSS value."
            ),
        ),
        (
            "rx.ui.flex",
            None,
            {"gapp": "2"},
            'rx.ui.flex: unknown layout prop "gapp". Did you mean "gap"?',
        ),
    ],
)
def test_errors(name: str, style: Any, layout: Any, message: str):
    """A style that cannot be compiled is refused with what to do about it.

    Args:
        name: The display name of the component.
        style: The style as written.
        layout: The layout props.
        message: The whole error message.
    """
    with pytest.raises(StyleError) as error:
        lower(name, style, layout)
    assert str(error.value) == message
    assert isinstance(error.value, ValueError)


def test_layers_merge_by_property_and_the_last_one_wins():
    """A later style replaces a property, or adds conditions to it."""
    props, replaced = lower_layer(
        "rx.ui.card",
        {
            "color": {"default": "black", ":hover": "blue"},
            "width": "1px",
            "outline_color": "red",
            "margin_top": "1px",
            "top": {":hover": {"default": "1px", XS: "2px"}},
            "left": {":hover": {"default": "1px", XS: "2px"}},
            "opacity": 1,
        },
    )
    assert replaced == ()
    later = lower_layer(
        "rx.ui.card",
        {
            "color": "green",
            "_focus": {"width": "2px"},
            "outline": WIDTH,
            "margin": "var(--gap)",
            "_hover": {"left": "3px", "_active": {"top": "4px"}},
            "opacity": None,
        },
    )
    assert later[1] == (*_REPLACES["outline"], *_REPLACES["margin"])
    apply_layer(props, later)
    assert finish(props) == Lowered({
        "color": "green",
        "width": {"default": "1px", ":focus": "2px"},
        "outline": WIDTH,
        "margin": "var(--gap)",
        "top": {":hover": {"default": "1px", XS: "2px", ":active": "4px"}},
        "left": {":hover": "3px"},
    })
    assert finish({"color": None}) == Lowered({})
    assert finish({"color": None, "top": 0}, unset=True) == Lowered({
        "color": None,
        "top": 0,
    })


def test_lowered_styles_compare_and_hash_by_what_they_compile_to():
    """Equal styles are one key, whatever the order of their properties."""
    first = lower("rx.ui.card", {"color": "red", "width": WIDTH, "_hover": {"top": 0}})
    second = lower("rx.ui.box", {"width": WIDTH, "_hover": {"top": 0}, "color": "red"})
    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1
    different = [
        lower("rx.ui.card", {"color": "red", "width": WIDTH, "_hover": {"top": 1}}),
        lower("rx.ui.card", {"color": "red", "width": SCALE, "_hover": {"top": 0}}),
        lower("rx.ui.card", {"color": "red", "width": WIDTH, "_focus": {"top": 0}}),
        lower("rx.ui.card", {"color": "red", "width": WIDTH}),
        Lowered(dict(first.style), (RUBY,)),
        Lowered(dict(first.style), (), StyleState.style),
    ]
    assert [style == first for style in different] == [False] * 6
    assert first != dict(first.style)
    assert lower("rx.ui.card", {}) is lower("rx.ui.card", None)
    assert repr(lower("rx.ui.card", {"color": rx.color("ruby", 9)})) == (
        "Lowered({'color': 'var(--ruby-9)'}, "
        "('$/reflex-ui/colors/ruby.stylex.js',), None)"
    )


def test_var_values_are_vars():
    """A Var in a lowered style is the Var that was written."""
    value = lower("rx.ui.card", {"width": WIDTH}).style["width"]
    assert isinstance(value, Var)
    assert value.equals(WIDTH)


@pytest.mark.parametrize(
    ("style", "expected", "imports"),
    [
        (
            {"padding": tokens.space[3]},
            _sides("padding", "", *["var(--space-3)"] * 4),
            (SPACE,),
        ),
        (
            {"padding": f"{tokens.space[2]} {tokens.space[4]}"},
            _sides(
                "padding",
                "",
                "var(--space-2)",
                "var(--space-4)",
                "var(--space-2)",
                "var(--space-4)",
            ),
            (SPACE,),
        ),
        (
            {"margin": f"0 auto {tokens.space[1]}"},
            _sides("margin", "", "0", "auto", "var(--space-1)", "auto"),
            (SPACE,),
        ),
        (
            {"gap": f"{tokens.space[1]} {tokens.space[2]}"},
            {"rowGap": "var(--space-1)", "columnGap": "var(--space-2)"},
            (SPACE,),
        ),
        (
            {"border_radius": tokens.radius[3]},
            {
                "borderTopLeftRadius": "var(--radius-3)",
                "borderTopRightRadius": "var(--radius-3)",
                "borderBottomRightRadius": "var(--radius-3)",
                "borderBottomLeftRadius": "var(--radius-3)",
            },
            ("$/reflex-ui/tokens/radius.stylex.js",),
        ),
        (
            {"border_color": tokens.gray.a[6]},
            _sides("border", "Color", *["var(--gray-a6)"] * 4),
            (GRAY,),
        ),
        (
            {"border": f"1px solid {tokens.accent[7]}"},
            _border(ALL_SIDES, "1px", "solid", "var(--accent-7)"),
            (ACCENT,),
        ),
        (
            {"background": tokens.color.panel},
            {"backgroundColor": "var(--color-panel)", "backgroundImage": "none"},
            ("$/reflex-ui/tokens/color.stylex.js",),
        ),
        # A shadow is a list of layers and a font family a list of fonts: a
        # shorthand that holds one is kept whole, as with any other property.
        (
            {"padding": tokens.shadow[1]},
            {"padding": "var(--shadow-1)"},
            ("$/reflex-ui/tokens/shadow.stylex.js",),
        ),
        (
            {"margin": f"{tokens.space[1]} {tokens.default.font_family}"},
            {"margin": "var(--space-1) var(--default-font-family)"},
            (SPACE, "$/reflex-ui/tokens/typography.stylex.js"),
        ),
        (
            {"padding": f"{tokens.space[1]} var(--mine)"},
            {"padding": "var(--space-1) var(--mine)"},
            (SPACE,),
        ),
        (
            {"padding": f"calc({tokens.space[1]} * 2) {tokens.space[2]}"},
            {"padding": "calc(var(--space-1) * 2) var(--space-2)"},
            (SPACE,),
        ),
        (
            {"font_size": tokens.font_size[2], "box_shadow": tokens.shadow[3]},
            {"fontSize": "var(--font-size-2)", "boxShadow": "var(--shadow-3)"},
            (
                "$/reflex-ui/tokens/shadow.stylex.js",
                "$/reflex-ui/tokens/typography.stylex.js",
            ),
        ),
    ],
)
def test_design_tokens(style: Any, expected: dict[str, Any], imports: tuple[str, ...]):
    """A token is its custom property: a shorthand gives one to each longhand.

    Args:
        style: The style as written.
        expected: The lowered properties.
        imports: The modules the style needs.
    """
    lowered = lower("rx.ui.card", style)
    assert lowered == Lowered(expected, imports)
    assert lowered.imports == imports


@pytest.mark.parametrize(
    ("layout", "message"),
    [
        (
            {"p": {"tablet": "1"}},
            (
                'rx.ui.flex: prop "p" is given a value under "tablet", which is not a '
                'breakpoint. Use "initial", "xs", "sm", "md", "lg" or "xl", or set a '
                "style, which takes any media query."
            ),
        ),
        (
            {"gap": ["1"] * 7},
            (
                'rx.ui.flex: layout prop "gap" has 7 responsive values, but there are '
                "only 6 breakpoints."
            ),
        ),
    ],
)
def test_layout_prop_breakpoint_errors(layout: dict[str, Any], message: str):
    with pytest.raises(StyleError) as error:
        lower("rx.ui.flex", None, layout)
    assert str(error.value) == message


def test_layout_props_keep_the_breakpoints_of_radix_whatever_the_app_has():
    """A prop is resolved as Radix Themes resolves it; a style follows the app."""
    original = tuple(breakpoints_values)
    set_breakpoints(("10px", "20px", "30px", "40px", "50px"))
    try:
        lowered = lower(
            "rx.ui.flex",
            {"width": rx.breakpoints(sm="2px")},
            {"spacing_x": rx.breakpoints(sm="2"), "spacing_y": ["1", "3"]},
        )
    finally:
        set_breakpoints(original)  # pyright: ignore [reportArgumentType]
    assert lowered.style == {
        "columnGap": {PROP_SM: "var(--space-2)"},
        "rowGap": {"default": "var(--space-1)", PROP_XS: "var(--space-3)"},
        "width": {"@media screen and (min-width: 20px)": "2px"},
    }


FADE = {"from": {"opacity": 1}, "to": {"opacity": 0}}
TINT = {"100%": {"background_color": tokens.accent[7]}}
FADE_SOURCE = '{"from": {"opacity": 1}, "to": {"opacity": 0}}'
TINT_SOURCE = '{"100%": {"backgroundColor": "var(--accent-7)"}}'
ACCENT_MODULE = "$/reflex-ui/tokens/accent.stylex.js"


def test_keyframes_hold_the_frames_of_each_animation_they_play():
    """One set of frames is one animation, several are played together."""
    one = keyframes(FADE)
    assert (one.sources, one.imports) == ((FADE_SOURCE,), ())
    assert repr(one) == f"Keyframes(({FADE_SOURCE!r},), ())"
    several = keyframes(FADE, TINT)
    assert (several.sources, several.imports) == (
        (FADE_SOURCE, TINT_SOURCE),
        (ACCENT_MODULE,),
    )
    # Equal by what they declare, in the order they play it.
    assert several == keyframes(FADE, TINT)
    assert hash(several) == hash(keyframes(FADE, TINT))
    assert several != keyframes(TINT, FADE)
    assert several != one
    lowered = lower(
        "rx.ui.box", {"animation_name": several, "animation_duration": "1s, 2s"}
    )
    assert lowered.style == {
        "animationName": several,
        "animationDuration": "1s, 2s",
    }
    assert lowered.imports == (ACCENT_MODULE,)


@pytest.mark.parametrize(
    ("frames", "message"),
    [
        (
            (FADE, {"to": "red"}),
            'rx.ui keyframes: the frame "to" must be a dict of styles, not str.',
        ),
        (
            (FADE, {"to": {"color": {"default": "red", ":hover": "blue"}}}),
            (
                'rx.ui keyframes: the style "color" of the frame "to" must be a '
                "literal: a frame takes no condition and nothing bound to state."
            ),
        ),
    ],
)
def test_keyframes_check_every_animation(frames: tuple[Any, ...], message: str):
    with pytest.raises(StyleError) as error:
        keyframes(*frames)
    assert str(error.value) == message


def test_keyframes_are_the_value_of_animation_name_alone():
    with pytest.raises(StyleError) as error:
        lower("rx.ui.box", {"animation_duration": keyframes(FADE, TINT)})
    assert str(error.value) == (
        'rx.ui.box: style "animation_duration" is given keyframes, which are '
        "the value of animation_name."
    )


def test_shorthand_kept_whole_replaces_the_longhands_written_before_it():
    """Within one style too, the later of a shorthand and its longhands wins."""
    # The shorthand cannot be split, so the longhand before it has to go:
    # StyleX would let a longhand win over the shorthand wherever it is.
    assert lower_layer(
        "rx.ui.box",
        {
            "margin_top": "1em",
            "_hover": {"margin_left": "2px"},
            "margin": "var(--gap)",
            "margin_bottom": "0",
        },
    ) == (
        {"margin": "var(--gap)", "marginBottom": "0"},
        _REPLACES["margin"],
    )
    # A layout prop is lowered first, and a style after it wins the same way.
    assert lower_layer("rx.ui.box", {"margin": "var(--gap)"}, {"mt": "2"}) == (
        {"margin": "var(--gap)"},
        _REPLACES["margin"],
    )
    # Under a condition the shorthand replaces nothing: the longhand stays.
    assert lower_layer(
        "rx.ui.box", {"margin_top": "1em", "_hover": {"margin": "var(--gap)"}}
    ) == ({"marginTop": "1em", "margin": {":hover": "var(--gap)"}}, ())
