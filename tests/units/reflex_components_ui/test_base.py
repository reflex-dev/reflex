"""Tests for reflex_components_ui.base."""

from collections.abc import Callable
from typing import ClassVar

import pytest
from reflex_base.config import get_config
from reflex_base.plugins import CompileContext
from reflex_base.utils.exceptions import ConfigError
from reflex_base.utils.serializers import serialize
from reflex_base.vars.base import Var
from reflex_components_ui.base import ComponentStyles, UIComponent
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style.emit import UnsupportedStyleError

import reflex as rx
from reflex.compiler import compiler

# A page whose only element was moved into a module of its own.
MEMO_PAGE = """import {Card_section_b8f6e6fad3a0fd8c010369e2de15b082} from "$/utils/components/Card_section_b8f6e6fad3a0fd8c010369e2de15b082"
import {Fragment,useEffect} from "react"
import {jsx} from "@emotion/react"





function Component() {


  return (
    jsx(Fragment,{},jsx(Card_section_b8f6e6fad3a0fd8c010369e2de15b082,{},"hello"),jsx("title",{}," | Index"),jsx("meta",{content:"",property:"og:image"},))
  )
}
Component.displayName = "Component(/)";

export default Component;
"""

# The module that renders the element, with the declaration of its style.
MEMO_MODULE = """
import {ReflexEvent,applyEventActions,isTrue,mergeSlotProps} from "$/utils/state"
import {addEvents} from "$/utils/context"
import {Fragment,memo,useCallback,useEffect} from "react"
import * as stylex from "@stylexjs/stylex"
import {jsx} from "@emotion/react"



const sx_b5d18f9eca = stylex.create({ s: {"color": {"default": "red", ":hover": "blue"}, "padding": "8px"} });


export const Card_section_b8f6e6fad3a0fd8c010369e2de15b082 = /*#__PURE__*/ (() => {
const Card_section_b8f6e6fad3a0fd8c010369e2de15b082 = memo(({children, ...rest}) => {
    const on_click_d7389fe0b34b5da3b1e38e11566dcc81 = useCallback(((_e) => (addEvents([(ReflexEvent("reflex___state____state.tests___units___reflex_components_ui___test_base____base_test_state.noop", ({  }), ({  })))], [_e], ({  })))), [])
    return(
        jsx("section",{...mergeSlotProps(rest, ({ onClick:on_click_d7389fe0b34b5da3b1e38e11566dcc81, ...stylex.props(sx_b5d18f9eca.s) }))},children)
    )
});
Card_section_b8f6e6fad3a0fd8c010369e2de15b082.displayName = "Card";
return Card_section_b8f6e6fad3a0fd8c010369e2de15b082;
})();
"""

# What the browser evaluates for a component held in state.
DYNAMIC_MODULE = (
    "//__reflex_evaluate:[]\n"
    "const React = window.__reflex.react;\n"
    "\n"
    "const {jsx} = window.__reflex['@emotion/react']\n"
    "const {Fragment,useEffect} = window.__reflex['react']\n"
    "const {pyOr} = window.__reflex['$/utils/state']\n"
    "\n"
    "export default function MySSRComponent () {\n"
    "  \n"
    "  return (\n"
    '    (jsx("div", ({className:"p-8",style:({ ["padding"] : "4px", ["zIndex"] : 2 })}), "hello"))\n'
    "  )\n"
    "}"
)


class Plain(UIComponent):
    """An element with no look of its own."""


class Card(UIComponent):
    """An element whose look has a condition."""

    tag = "section"

    styles: ClassVar[ComponentStyles] = {
        "base": {"color": {"default": "red", ":hover": "blue"}, "padding": "8px"},
    }


class Variants(UIComponent):
    """An element whose look depends on a prop."""

    styles: ClassVar[ComponentStyles] = {
        "variants": {"size": {"1": {"padding": "4px"}}}
    }


class BaseTestState(rx.State):
    """State the styles and class names are bound to."""

    color: str = "red"
    names: str = "p-8"

    @rx.event
    def noop(self):
        """Do nothing."""


def test_rendering_without_the_plugin_says_how_to_configure_it(
    monkeypatch: pytest.MonkeyPatch, compile_page: Callable[..., CompileContext]
):
    monkeypatch.setattr(get_config(), "plugins", [])
    with pytest.raises(ConfigError) as raised:
        compile_page(lambda: Card.create("hello"))
    assert (
        str(raised.value)
        == "rx.ui components need rx.plugins.UIPlugin() in rxconfig.py plugins."
    )
    with pytest.raises(ConfigError) as raised:
        Card.create("hello").render()
    assert (
        str(raised.value)
        == "rx.ui components need rx.plugins.UIPlugin() in rxconfig.py plugins."
    )


def test_element_without_styles_is_a_plain_element(ui_plugin: UIPlugin):
    component = Plain.create("hello", class_name="p-8")
    assert component.render() == {
        "name": '"div"',
        "props": ['className:"p-8"'],
        "children": [{"contents": '"hello"'}],
    }
    assert component._get_all_custom_code() == {}


def test_style_is_spread_from_a_declaration_and_never_a_css_prop(ui_plugin: UIPlugin):
    """The user's style is merged over the component's, by property."""
    component = Card.create("hello", style={"padding": "4px", "margin_top": 2})
    assert component._get_all_custom_code() == {
        'const sx_5579d75d4f = stylex.create({ s: {"color": {"default": "red", '
        '":hover": "blue"}, "padding": "4px", "marginTop": 2} });': None
    }
    assert component.render() == {
        "name": '"section"',
        "props": ["...stylex.props(sx_5579d75d4f.s)"],
        "children": [{"contents": '"hello"'}],
    }
    assert component._get_style() == {}


def test_literal_class_names_fold_into_the_spread(ui_plugin: UIPlugin):
    """A spread would replace a className prop, so there is only the spread."""
    component = Card.create(class_name=["p-8", "m-2"], custom_attrs={"role": "note"})
    assert component.render()["props"] == [
        'role:"note"',
        '...stylex.props(sx_b5d18f9eca.s, { $$css: true, className: "p-8 m-2" })',
    ]


def test_class_names_from_state_are_joined_with_the_folded_ones(ui_plugin: UIPlugin):
    component = Card.create(class_name=BaseTestState.names)
    assert component.render()["props"] == [
        (
            f'className:({BaseTestState.names!s}) + " " + '
            "stylex.props(sx_b5d18f9eca.s).className"
        )
    ]


@pytest.mark.parametrize(
    ("create", "message"),
    [
        (
            lambda: Card.create(style={"color": BaseTestState.color}),
            (
                'rx.ui.card: the style "color" is bound to state, which rx.ui '
                "components cannot compile yet. Give it a literal value, or set it "
                "from state with a class_name."
            ),
        ),
        (
            lambda: Card.create(style={"_hover": {"color": "blue"}}),
            (
                'rx.ui.card: the style "_hover" is a nested block or a list, which '
                "rx.ui components cannot compile yet. Use flat properties with literal "
                "values."
            ),
        ),
        (
            lambda: Card.create(style={"width": ["100%", "50%"]}),
            (
                'rx.ui.card: the style "width" is a nested block or a list, which '
                "rx.ui components cannot compile yet. Use flat properties with literal "
                "values."
            ),
        ),
        (
            lambda: Variants.create(),
            "rx.ui.variants: variant and compound styles are not compiled yet.",
        ),
    ],
)
def test_style_that_cannot_be_compiled_yet_is_an_error(
    ui_plugin: UIPlugin, create: Callable[[], UIComponent], message: str
):
    component = create()
    with pytest.raises(UnsupportedStyleError) as raised:
        component.render()
    assert str(raised.value) == message
    with pytest.raises(UnsupportedStyleError) as raised:
        component._get_all_custom_code()
    assert str(raised.value) == message


def test_declaration_follows_the_element_into_a_memo_module(
    ui_plugin: UIPlugin, compile_page: Callable[..., CompileContext]
):
    """StyleX only folds a style declared in the module that renders it.

    An event handler makes the compiler move the element into a module of its
    own: the declaration and the import go there, and leave the page.
    """
    ctx = compile_page(lambda: Card.create("hello", on_click=BaseTestState.noop))
    assert ctx.compiled_pages["/"].output_code == MEMO_PAGE
    ((_, memo_module),) = compiler.compile_memo_components(
        tuple(ctx.auto_memo_components.values())
    )[0]
    assert memo_module == MEMO_MODULE


def test_dynamic_component_falls_back_to_an_inline_style():
    """Code evaluated in the browser has no build, no plugin and no StyleX."""
    component = Plain.create(
        "hello", style={"padding": "4px", "z_index": 2}, class_name="p-8"
    )
    assert serialize(component) == DYNAMIC_MODULE


def test_dynamic_component_cannot_have_a_conditional_style():
    with pytest.raises(UnsupportedStyleError) as raised:
        serialize(Card.create("hello"))
    assert str(raised.value) == (
        'rx.ui.card: the style "color" has conditions ("default", ":hover"), which '
        "a component rendered from state cannot apply: its code is evaluated in "
        "the browser and never reaches the StyleX compiler. Use an unconditional "
        "value there, or render the component in a page and show it with rx.cond."
    )


def test_var_style_values_reach_the_error_of_the_emitter(ui_plugin: UIPlugin):
    """A state-bound value is not mistaken for a literal on its way down."""
    component = Card.create(style={"color": Var("state.color", _var_type=str)})
    with pytest.raises(UnsupportedStyleError) as raised:
        component.render()
    assert str(raised.value) == (
        'rx.ui.card: the style "color" is bound to state, which rx.ui components '
        "cannot compile yet. Give it a literal value, or set it from state with a "
        "class_name."
    )
