"""Tests for reflex_components_ui.style.emit."""

import pytest
from reflex_base.vars.base import Var
from reflex_components_ui.style.emit import (
    StyleXStyle,
    UnsupportedStyleError,
    emit,
    inline,
    props_call,
)


def test_emit_declares_a_style_named_after_its_content():
    """Literals and condition maps are written as StyleX takes them."""
    style = {
        "padding": "var(--space-3)",
        "lineHeight": 1.5,
        "zIndex": 2,
        "color": {
            "default": "red",
            ":hover": {"default": "blue", "@media (min-width: 768px)": "green"},
        },
    }
    assert emit(style, "rx.ui.box") == StyleXStyle(
        declaration=(
            'const sx_163452d900 = stylex.create({ s: {"padding": "var(--space-3)", '
            '"lineHeight": 1.5, "zIndex": 2, "color": {"default": "red", ":hover": '
            '{"default": "blue", "@media (min-width: 768px)": "green"}}} });'
        ),
        ref="sx_163452d900.s",
    )


def test_emit_is_deterministic_and_tells_styles_apart():
    """Equal styles share a declaration; different ones never share a name."""
    assert emit({"padding": "4px"}, "rx.ui.box") == emit(
        {"padding": "4px"}, "rx.ui.flex"
    )
    names = {
        style.ref
        for source in ({"padding": "4px"}, {"padding": "5px"}, {"padding": 4})
        if (style := emit(source, "rx.ui.box")) is not None
    }
    assert len(names) == 3


def test_emit_has_nothing_to_declare_for_an_empty_style():
    assert emit({}, "rx.ui.box") is None


@pytest.mark.parametrize(
    ("style", "message"),
    [
        (
            {"color": Var("state.color")},
            (
                'rx.ui.box: the style "color" is bound to state, which rx.ui components '
                "cannot compile yet. Give it a literal value, or set it from state with "
                "a class_name."
            ),
        ),
        (
            {"color": {"default": "red", ":hover": Var("state.color")}},
            (
                'rx.ui.box: the style "color" under ":hover" is bound to state, which '
                "rx.ui components cannot compile yet. Give it a literal value, or set it "
                "from state with a class_name."
            ),
        ),
        (
            {"width": ["100%", "50%"]},
            (
                "rx.ui.box: the style \"width\" is ['100%', '50%'], a list. Use a string "
                "or a number, or a mapping from condition to value such as "
                '{"default": "red", ":hover": "blue"}.'
            ),
        ),
        (
            {"display": True},
            (
                'rx.ui.box: the style "display" is True, a bool. Use a string or a '
                "number, or a mapping from condition to value such as "
                '{"default": "red", ":hover": "blue"}.'
            ),
        ),
    ],
)
def test_emit_rejects_what_stylex_cannot_compile(style: dict, message: str):
    with pytest.raises(UnsupportedStyleError) as raised:
        emit(style, "rx.ui.box")
    assert str(raised.value) == message


def test_props_call_applies_styles_in_order_with_literal_class_names():
    assert props_call(("sx_a.s",)) == "stylex.props(sx_a.s)"
    assert props_call(("sx_a.s", "sx_b.s")) == "stylex.props(sx_a.s, sx_b.s)"
    assert props_call(("sx_a.s",), 'p-8 "quoted"') == (
        'stylex.props(sx_a.s, { $$css: true, className: "p-8 \\"quoted\\"" })'
    )
    assert props_call(("sx_a.s",), "") == "stylex.props(sx_a.s)"


def test_inline_keeps_literals():
    assert inline({"padding": "4px", "zIndex": 2, "opacity": 0.5}, "rx.ui.box") == {
        "padding": "4px",
        "zIndex": 2,
        "opacity": 0.5,
    }


@pytest.mark.parametrize(
    ("style", "message"),
    [
        (
            {"color": {"default": "red", ":hover": "blue"}},
            (
                'rx.ui.box: the style "color" has conditions ("default", ":hover"), '
                "which a component rendered from state cannot apply: its code is "
                "evaluated in the browser and never reaches the StyleX compiler. Use an "
                "unconditional value there, or render the component in a page and show "
                "it with rx.cond."
            ),
        ),
        (
            {"color": Var("state.color")},
            (
                'rx.ui.box: the style "color" is bound to state, which rx.ui components '
                "cannot compile yet. Give it a literal value, or set it from state with "
                "a class_name."
            ),
        ),
    ],
)
def test_inline_rejects_what_an_inline_style_cannot_hold(style: dict, message: str):
    with pytest.raises(UnsupportedStyleError) as raised:
        inline(style, "rx.ui.box")
    assert str(raised.value) == message
