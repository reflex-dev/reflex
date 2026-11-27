"""Tests for merging the style table of a component with a user's style."""

import re
from typing import Any

import pytest
from reflex_base.breakpoints import breakpoints_values, set_breakpoints
from reflex_base.vars.base import LiteralVar
from reflex_components_ui.style.lower import Lowered, StyleError
from reflex_components_ui.style.merge import (
    Alternatives,
    ComponentStyles,
    Merged,
    merge,
)

import reflex as rx

RUBY = "$/reflex-ui/colors/ruby.stylex.js"
SPACE = "$/reflex-ui/tokens/space.stylex.js"
ACCENT = "$/reflex-ui/tokens/accent.stylex.js"
GRAY = "$/reflex-ui/tokens/gray.stylex.js"
# The module of each token the expected styles of these tests name.
TOKEN_MODULES = {"ruby": RUBY, "space": SPACE, "accent": ACCENT, "gray": GRAY}
XS = "@media screen and (min-width: 30em)"


class MergeState(rx.State):
    """State whose fields are bound to props and styles."""

    variant: rx.Field[str] = rx.field("solid")
    size: rx.Field[str] = rx.field("1")
    loading: rx.Field[bool] = rx.field(False)
    style: rx.Field[dict[str, str]] = rx.field({})


VARIANT = MergeState.variant
SIZE = MergeState.size
LOADING = MergeState.loading

BUTTON: ComponentStyles = {
    "base": {
        "display": "inline-flex",
        "color": "black",
        "margin_top": "1px",
        "outline_width": "1px",
    },
    "variants": {
        "variant": {
            "solid": {
                "background_color": {
                    "default": "var(--accent-9)",
                    ":hover": "var(--accent-10)",
                },
                "color": "white",
            },
            "soft": {"background_color": rx.color("ruby", 3)},
            "ghost": {"outline": "none"},
        },
        "size": {
            "1": {"height": "var(--space-5)"},
            "2": {"height": "var(--space-6)", "_hover": {"color": "gray"}},
        },
        "loading": {"true": {"opacity": 0.5}},
    },
    "compound": [
        {"props": {"variant": "solid", "size": "2"}, "style": {"font_weight": "700"}},
        {"props": {"loading": "true"}, "style": {"cursor": "wait"}},
    ],
    "parts": {
        "icon": {
            "base": {"width": "1em"},
            "variants": {"size": {"2": {"width": "2em"}}},
            "parts": {"dot": {"base": {"top": 0}}},
        },
        "label": {"base": {"flex_grow": 1}},
    },
}

BASE = {
    "display": "inline-flex",
    "color": "black",
    "marginTop": "1px",
    "outlineWidth": "1px",
}


def _lowered(style: dict[str, Any], inline: Any = None) -> Lowered:
    """Build the lowered style a test expects, with the modules its values need.

    Args:
        style: The lowered properties.
        inline: A Var holding a whole dict of styles.

    Returns:
        The lowered style, importing the module of every token it names.
    """
    found = set(re.findall(r"var\(--([a-z]+)-", repr(style)))
    return Lowered(
        style, tuple(sorted([TOKEN_MODULES[word] for word in found])), inline
    )


SOLID_BACKGROUND = {"default": "var(--accent-9)", ":hover": "var(--accent-10)"}
DOT = Merged(Lowered({"top": 0}))
LABEL = Merged(Lowered({"flexGrow": 1}))
SMALL_PARTS = {
    "icon": Merged(Lowered({"width": "1em"}), (), {"dot": DOT}),
    "label": LABEL,
}
LARGE_PARTS = {
    "icon": Merged(Lowered({"width": "2em"}), (), {"dot": DOT}),
    "label": LABEL,
}


@pytest.mark.parametrize(
    ("props", "style", "expected", "parts"),
    [
        (None, None, BASE, SMALL_PARTS),
        ({}, {}, BASE, SMALL_PARTS),
        (
            {"variant": "unknown", "size": None, "disabled": True},
            None,
            BASE,
            SMALL_PARTS,
        ),
        (
            {"variant": "solid", "size": "1"},
            None,
            {
                **BASE,
                "backgroundColor": SOLID_BACKGROUND,
                "color": "white",
                "height": "var(--space-5)",
            },
            SMALL_PARTS,
        ),
        (
            {"variant": "solid", "size": "2", "loading": True},
            None,
            {
                **BASE,
                "backgroundColor": SOLID_BACKGROUND,
                "color": {"default": "white", ":hover": "gray"},
                "height": "var(--space-6)",
                "opacity": 0.5,
                "fontWeight": "700",
                "cursor": "wait",
            },
            LARGE_PARTS,
        ),
        (
            {"variant": "ghost", "size": 2, "loading": False},
            None,
            {
                "display": "inline-flex",
                "color": {"default": "black", ":hover": "gray"},
                "marginTop": "1px",
                "outline": "none",
                "height": "var(--space-6)",
            },
            LARGE_PARTS,
        ),
        (
            {"variant": LiteralVar.create("soft"), "loading": LiteralVar.create(True)},
            None,
            {
                **BASE,
                "backgroundColor": "var(--ruby-3)",
                "opacity": 0.5,
                "cursor": "wait",
            },
            SMALL_PARTS,
        ),
        (
            {"variant": "solid", "size": "2"},
            {
                "color": "pink",
                "_hover": {"background_color": "red"},
                "_focus": {"height": "1px"},
                "margin": "0",
                "font_weight": None,
                "width": ["1px", "2px"],
            },
            {
                "display": "inline-flex",
                "color": "pink",
                "marginTop": "0",
                "marginRight": "0",
                "marginBottom": "0",
                "marginLeft": "0",
                "outlineWidth": "1px",
                "backgroundColor": {"default": "var(--accent-9)", ":hover": "red"},
                "height": {"default": "var(--space-6)", ":focus": "1px"},
                "width": {"default": "1px", XS: "2px"},
            },
            LARGE_PARTS,
        ),
        (
            {"variant": "solid"},
            {
                "background_color": "red",
                "outline": "2px solid",
                "margin": MergeState.size,
            },
            {
                "display": "inline-flex",
                "color": "white",
                "backgroundColor": "red",
                "outline": "2px solid",
                "margin": SIZE,
            },
            SMALL_PARTS,
        ),
    ],
)
def test_merge_order(props: Any, style: Any, expected: dict[str, Any], parts: Any):
    """Base, variants, compound styles and the user style merge in that order.

    Args:
        props: The props of the element.
        style: The style the user wrote.
        expected: The lowered properties of the element.
        parts: The merged styles of its inner elements.
    """
    merged = merge("rx.ui.button", BUTTON, props, style)
    assert merged == Merged(_lowered(expected), (), parts)
    assert merged.dynamic == ()
    assert list(merged.parts) == ["icon", "label"]


def test_layout_props_merge_between_the_table_and_the_style():
    """A layout prop wins over the table and loses to the user style."""
    assert merge(
        "rx.ui.button",
        BUTTON,
        {"size": "1"},
        {"margin_left": "auto"},
        {"m": "2", "gap": "1"},
    ) == Merged(
        _lowered({
            "display": "inline-flex",
            "color": "black",
            "marginTop": "var(--space-2)",
            "marginRight": "var(--space-2)",
            "marginBottom": "var(--space-2)",
            "marginLeft": "auto",
            "outlineWidth": "1px",
            "height": "var(--space-5)",
            "rowGap": "var(--space-1)",
            "columnGap": "var(--space-1)",
        }),
        (),
        SMALL_PARTS,
    )


def test_whole_dict_var_style_is_carried_with_the_table_styles():
    """A Var holding the user style leaves the table styles compiled."""
    merged = merge("rx.ui.button", BUTTON, {"size": "1"}, MergeState.style)
    assert merged == Merged(
        _lowered({**BASE, "height": "var(--space-5)"}, MergeState.style),
        (),
        SMALL_PARTS,
    )
    assert merged != merge("rx.ui.button", BUTTON, {"size": "1"})


def test_identical_inputs_give_one_hashable_result():
    """The emitter can share a declaration between elements that match."""
    plain = merge("rx.ui.button", BUTTON, {"variant": "solid", "size": "1"})
    assert merge("rx.ui.button", BUTTON, {"size": "1", "variant": "solid"}) is plain
    assert merge("rx.ui.button", BUTTON, {"size": 1, "variant": "solid"}) is plain

    styled = [
        merge("rx.ui.button", BUTTON, {"size": "1"}, {"color": SIZE, "top": 0}),
        merge("rx.ui.button", BUTTON, {"size": "1"}, {"top": 0, "color": SIZE}),
        merge("rx.ui.button", BUTTON, {"size": SIZE}, {"color": SIZE, "top": 0}),
        merge("rx.ui.button", BUTTON, {"size": SIZE}, {"color": SIZE, "top": 0}),
    ]
    assert styled[0] == styled[1]
    assert styled[2] == styled[3]
    assert styled[0] != styled[2]
    assert styled[0] != plain
    assert styled[0] != styled[0].style
    assert [hash(merged) for merged in styled[:2]] == [hash(styled[0])] * 2
    assert len(set(styled)) == 2
    assert styled[2].dynamic[0] == styled[3].dynamic[0]
    assert styled[2].dynamic[0] != styled[2]
    assert len({styled[2].dynamic[0], styled[3].dynamic[0]}) == 1


def test_state_bound_variant_returns_every_value_unresolved():
    """A prop bound to state gives one alternative per value of its variant."""
    merged = merge(
        "rx.ui.button",
        BUTTON,
        {"variant": VARIANT, "size": "2"},
        {"color": "pink", "_hover": {"background_color": "red"}},
    )
    assert merged == Merged(
        _lowered({
            **BASE,
            "color": "pink",
            "height": "var(--space-6)",
            "backgroundColor": {":hover": "red"},
        }),
        (
            Alternatives(
                ("variant",),
                (VARIANT,),
                {
                    ("solid",): _lowered({
                        "backgroundColor": {
                            "default": "var(--accent-9)",
                            ":hover": "red",
                        },
                        "fontWeight": "700",
                    }),
                    ("soft",): _lowered({
                        "backgroundColor": {
                            "default": "var(--ruby-3)",
                            ":hover": "red",
                        }
                    }),
                    ("ghost",): _lowered({"outline": "none", "outlineWidth": None}),
                },
            ),
        ),
        LARGE_PARTS,
    )
    assert merged.dynamic[0].props == ("variant",)
    assert merged.dynamic[0].vars[0].equals(VARIANT)
    assert list(merged.dynamic[0].values) == [("solid",), ("soft",), ("ghost",)]
    assert merged.dynamic[0].values["ghost",].style == {
        "outline": "none",
        "outlineWidth": None,
    }


def test_independent_state_bound_props_are_separate_alternatives():
    """Props that set different properties are picked one by one."""
    assert merge(
        "rx.ui.button", BUTTON, {"variant": "soft", "size": SIZE, "loading": LOADING}
    ) == Merged(
        _lowered({**BASE, "backgroundColor": "var(--ruby-3)"}),
        (
            Alternatives(
                ("size",),
                (SIZE,),
                {
                    ("1",): _lowered({"height": "var(--space-5)"}),
                    ("2",): _lowered({
                        "height": "var(--space-6)",
                        "color": {"default": "black", ":hover": "gray"},
                    }),
                },
            ),
            Alternatives(
                ("loading",),
                (LOADING,),
                {("true",): _lowered({"opacity": 0.5, "cursor": "wait"})},
            ),
        ),
        {
            "icon": Merged(
                _lowered({"width": "1em"}),
                (
                    Alternatives(
                        ("size",), (SIZE,), {("2",): _lowered({"width": "2em"})}
                    ),
                ),
                {"dot": DOT},
            ),
            "label": LABEL,
        },
    )


def test_state_bound_props_that_depend_on_each_other_are_one_alternative():
    """Props that share a property or a compound style are picked together."""
    solid = {"backgroundColor": SOLID_BACKGROUND}
    soft = _lowered({"backgroundColor": "var(--ruby-3)"})
    ghost = {"outline": "none", "outlineWidth": None}
    assert merge(
        "rx.ui.button", BUTTON, {"variant": VARIANT, "size": SIZE}
    ).dynamic == (
        Alternatives(
            ("variant", "size"),
            (VARIANT, SIZE),
            {
                ("solid", "1"): _lowered({
                    **solid,
                    "color": "white",
                    "height": "var(--space-5)",
                }),
                ("solid", "2"): _lowered({
                    **solid,
                    "color": {"default": "white", ":hover": "gray"},
                    "height": "var(--space-6)",
                    "fontWeight": "700",
                }),
                ("soft", "1"): _lowered({**soft.style, "height": "var(--space-5)"}),
                ("soft", "2"): _lowered({
                    **soft.style,
                    "height": "var(--space-6)",
                    "color": {"default": "black", ":hover": "gray"},
                }),
                ("ghost", "1"): _lowered({**ghost, "height": "var(--space-5)"}),
                ("ghost", "2"): _lowered({
                    **ghost,
                    "height": "var(--space-6)",
                    "color": {"default": "black", ":hover": "gray"},
                }),
            },
        ),
    )


def test_state_bound_prop_that_only_a_compound_style_reads():
    """The values a compound style names are the alternatives of its prop."""
    table: ComponentStyles = {
        "base": {"color": "black"},
        "variants": {"size": {"1": {"top": 0}}},
        "compound": [
            {"props": {"size": "1", "tone": "loud"}, "style": {"color": "red"}},
            {"props": {"tone": "quiet"}, "style": {"color": "gray"}},
        ],
    }
    tone = MergeState.variant
    assert merge("rx.ui.badge", table, {"size": "1", "tone": tone}) == Merged(
        Lowered({"color": "black", "top": 0}),
        (
            Alternatives(
                ("tone",),
                (tone,),
                {
                    ("loud",): Lowered({"color": "red"}),
                    ("quiet",): Lowered({"color": "gray"}),
                },
            ),
        ),
    )
    assert merge("rx.ui.badge", table, {"tone": tone}, {"color": "blue"}) == Merged(
        Lowered({"color": "blue"})
    )
    assert repr(merge("rx.ui.badge", table, {"tone": "quiet"})) == (
        "Merged(Lowered({'color': 'gray'}, (), None), (), {})"
    )
    assert repr(Alternatives(("tone",), (), {("loud",): Lowered({"top": 0})})) == (
        "Alternatives(('tone',), (), {('loud',): Lowered({'top': 0}, (), None)})"
    )


def test_table_is_lowered_again_when_the_breakpoints_change():
    """A table lowered before `set_breakpoints` does not keep the old widths."""
    table: ComponentStyles = {"base": {"width": ["1px", "2px"]}}
    before = merge("rx.ui.box", table)
    original = tuple(breakpoints_values)
    set_breakpoints(("10px", "20px", "30px", "40px", "50px"))
    try:
        changed = merge("rx.ui.box", table)
    finally:
        set_breakpoints(original)  # pyright: ignore [reportArgumentType]
    assert before == Merged(Lowered({"width": {"default": "1px", XS: "2px"}}))
    assert changed == Merged(
        Lowered({
            "width": {"default": "1px", "@media screen and (min-width: 10px)": "2px"}
        })
    )
    assert merge("rx.ui.box", table) == before


@pytest.mark.parametrize(
    ("table", "style", "message"),
    [
        (
            {"variant": {"size": {"1": {"top": 0}}}},
            None,
            (
                'rx.ui.card: unknown key "variant" in a style table. Use "base", '
                '"variants", "compound" or "parts".'
            ),
        ),
        (
            {"variants": {"size": {"1": {"heght": "1em"}}}},
            None,
            'rx.ui.card: unknown CSS property "heght". Did you mean "height"?',
        ),
        (
            {"parts": {"thumb": {"base": {"& > div": {"top": 0}}}}},
            None,
            (
                'rx.ui.card: style key "& > div" is a nested selector, which rx.ui '
                "styles do not support. Style the child component directly, or keep "
                "rx.card for this element."
            ),
        ),
        (
            {"compound": [{"props": {"size": "1"}, "style": {"colr": "red"}}]},
            None,
            'rx.ui.card: unknown CSS property "colr". Did you mean "color"?',
        ),
        (
            {"base": {"top": 0}},
            {"paddng": "1em"},
            'rx.ui.card: unknown CSS property "paddng". Did you mean "padding"?',
        ),
    ],
)
def test_errors(table: Any, style: Any, message: str):
    """A table or a style that cannot be compiled is refused in full.

    Args:
        table: The style table.
        style: The style the user wrote.
        message: The whole error message.
    """
    with pytest.raises(StyleError) as error:
        merge("rx.ui.card", table, None, style)
    assert str(error.value) == message
