"""Tests for reflex_components_ui.props."""

from typing import Any

import pytest
from reflex_base.vars.base import LiteralVar, Var
from reflex_components_ui.props import style_before, style_props
from reflex_components_ui.style import StyleError

import reflex as rx

NAMES = ("width", "min_width")


def test_style_props_moves_the_props_before_the_style():
    """A prop named after a CSS property is a style the element's own wins over."""
    props: dict[str, Any] = {
        "width": "10px",
        "min_width": LiteralVar.create("5px"),
        "id": "label",
        "style": {"width": "20px"},
    }
    style_props("rx.ui.thing", props, NAMES)
    assert props == {
        "id": "label",
        "style": [{"width": "10px", "min_width": "5px"}, {"width": "20px"}],
    }
    props = {"width": "10px", "style": [{"color": "red"}, {"color": "blue"}]}
    style_props("rx.ui.thing", props, NAMES)
    assert props == {"style": [{"width": "10px"}, {"color": "red"}, {"color": "blue"}]}


def test_style_props_reads_a_value_per_breakpoint_of_radix_themes():
    """The breakpoints are those of every prop, in their order."""
    props: dict[str, Any] = {
        "width": rx.breakpoints(lg="40px", initial="10px", xs="20px"),
        "min_width": rx.breakpoints(xs="5px"),
    }
    style_props("rx.ui.thing", props, NAMES)
    assert props == {
        "style": {
            "width": "10px",
            "@media (min-width: 520px)": {"width": "20px", "min_width": "5px"},
            "@media (min-width: 1280px)": {"width": "40px"},
        }
    }
    assert list(props["style"]) == [
        "width",
        "@media (min-width: 520px)",
        "@media (min-width: 1280px)",
    ]


def test_style_props_keeps_a_value_bound_to_state_and_leaves_the_rest():
    """A Var is a style like any other, and props that are not given add nothing."""
    width = Var("state.width", _var_type=str)
    props: dict[str, Any] = {"width": width, "max_width": "1px"}
    style_props("rx.ui.thing", props, NAMES)
    assert props == {"max_width": "1px", "style": {"width": width}}
    props = {"id": "label"}
    style_props("rx.ui.thing", props, NAMES)
    assert props == {"id": "label"}


def test_style_props_rejects_a_key_that_is_no_breakpoint():
    """A value under anything but a breakpoint is an error that names them."""
    with pytest.raises(StyleError) as error:
        style_props("rx.ui.thing", {"width": {"huge": "1px"}}, NAMES)
    assert str(error.value) == (
        'rx.ui.thing: prop "width" is given a value under "huge", which is not '
        'a breakpoint. Use "initial", "xs", "sm", "md", "lg" or "xl", or set a '
        "style, which takes any media query."
    )


def test_style_before_puts_styles_under_the_ones_given():
    """What a component works out is the first style: the ones given win."""
    worked_out = {"width": "1px"}
    props: dict[str, Any] = {}
    style_before(props, worked_out)
    assert props == {"style": {"width": "1px"}}

    props = {"style": {"width": "2px"}}
    style_before(props, worked_out)
    assert props == {"style": [{"width": "1px"}, {"width": "2px"}]}

    props = {"style": [{"width": "2px"}, {"color": "red"}]}
    style_before(props, worked_out)
    assert props == {"style": [{"width": "1px"}, {"width": "2px"}, {"color": "red"}]}
