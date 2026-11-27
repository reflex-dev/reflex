"""Tests for reflex_components_ui.base."""

from collections.abc import Callable
from typing import Any, ClassVar, Literal

import pytest
from reflex_base.components.component import Component
from reflex_base.components.memo import MEMOS
from reflex_base.config import get_config
from reflex_base.plugins import CompileContext
from reflex_base.utils.exceptions import ConfigError
from reflex_base.utils.serializers import serialize
from reflex_base.vars.base import Var
from reflex_components_ui import tokens
from reflex_components_ui.base import Part, UIComponent
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import ComponentStyles, StyleError
from reflex_components_ui.themes import LiteralAccentColor, ThemeError

import reflex as rx
from reflex.compiler import compiler

# A page whose elements use the tokens of two modules, two of them equally.
PAGE = """import * as stylex from "@stylexjs/stylex"
import "$/reflex-ui/colors/jade.stylex.js"
import "$/reflex-ui/colors/ruby.stylex.js"
import {Fragment,useEffect} from "react"
import {jsx} from "@emotion/react"



const sx_7e30cd30d8 = stylex.create({ s: {"color": "var(--ruby-9)", "top": "8px"} });
const sx_7e30cd30d8_c = stylex.props(sx_7e30cd30d8.s).className;
const sx_f17eb59c2d = stylex.create({ s: {"backgroundColor": "var(--jade-3)"} });
const sx_f17eb59c2d_c = stylex.props(sx_f17eb59c2d.s).className;

function Component() {


  return (
    jsx(Fragment,{},jsx("main",{},jsx("section",{className:sx_7e30cd30d8_c},"ruby"),jsx("section",{className:sx_7e30cd30d8_c},"again"),jsx("div",{className:sx_f17eb59c2d_c},"jade")),jsx("title",{}," | Index"),jsx("meta",{content:"",property:"og:image"},))
  )
}
Component.displayName = "Component(/)";

export default Component;
"""

# A page whose only element was moved into a module of its own.
MEMO_PAGE = """import {Button_button_f1bbe1600e526de2c75f843fcd30a1d1} from "$/utils/components/Button_button_f1bbe1600e526de2c75f843fcd30a1d1"
import {Fragment,useEffect} from "react"
import {jsx} from "@emotion/react"





function Component() {


  return (
    jsx(Fragment,{},jsx(Button_button_f1bbe1600e526de2c75f843fcd30a1d1,{},"hello"),jsx("title",{}," | Index"),jsx("meta",{content:"",property:"og:image"},))
  )
}
Component.displayName = "Component(/)";

export default Component;
"""

# The module that renders the element: its declaration, the table of its
# bound prop, the import of the tokens it uses and the state its styles read.
MEMO_MODULE = """
import {isTrue,mergeSlotProps} from "$/utils/state"
import {useStateContext} from "$/utils/context-registry"
import * as stylex from "@stylexjs/stylex"
import "$/reflex-ui/colors/ruby.stylex.js"
import {jsx} from "@emotion/react"
import {Fragment,memo,useEffect} from "react"



const sx_a860bb1ca1 = stylex.create({ s: {"width": "var(--v0)", "borderTopColor": "var(--ruby-9)"}, a0_0: {"color": "white", "backgroundColor": "black"}, a0_1: {"color": "black", "opacity": 0.5}, a0: {"color": "black"} });
const sx_a860bb1ca1_c = stylex.props(sx_a860bb1ca1.s).className;
const sx_a860bb1ca1_0 = { __proto__: null, "solid": stylex.props(sx_a860bb1ca1.a0_0).className, "soft": stylex.props(sx_a860bb1ca1.a0_1).className };
const sx_a860bb1ca1_0d = stylex.props(sx_a860bb1ca1.a0).className;


export const Button_button_f1bbe1600e526de2c75f843fcd30a1d1 = /*#__PURE__*/ (() => {
const Button_button_f1bbe1600e526de2c75f843fcd30a1d1 = memo(({children, ...rest}) => {
    const reflex___state____state__tests___units___reflex_components_ui___test_base____base_test_state = useStateContext("reflex___state____state.tests___units___reflex_components_ui___test_base____base_test_state", ["kind_rx_state_", "color_rx_state_"])
    return(
        jsx("button",{...mergeSlotProps(rest, ({ className:sx_a860bb1ca1_c + " " + (sx_a860bb1ca1_0[reflex___state____state__tests___units___reflex_components_ui___test_base____base_test_state.kind_rx_state_] ?? sx_a860bb1ca1_0d), style:({ "--v0": (reflex___state____state__tests___units___reflex_components_ui___test_base____base_test_state.color_rx_state_) ?? "initial" }) }))},children)
    )
});
Button_button_f1bbe1600e526de2c75f843fcd30a1d1.displayName = "Button";
return Button_button_f1bbe1600e526de2c75f843fcd30a1d1;
})();
"""

# The module of an rx.memo component, which is named after where it is defined.
RX_MEMO_MODULE = """
import {isTrue} from "$/utils/state"
import * as stylex from "@stylexjs/stylex"
import "$/reflex-ui/colors/ruby.stylex.js"
import {jsx} from "@emotion/react"
import {Fragment,memo,useEffect} from "react"



const sx_7e30cd30d8 = stylex.create({ s: {"color": "var(--ruby-9)", "top": "8px"} });
const sx_7e30cd30d8_c = stylex.props(sx_7e30cd30d8.s).className;




export const RubyCard_87d7d58e = /*#__PURE__*/ (() => {
const RubyCard_87d7d58e = memo(({}) => {
<no hooks>
    return(
        jsx("section",{className:sx_7e30cd30d8_c},"ruby")
    )
});
RubyCard_87d7d58e.displayName = "RubyCard";
return RubyCard_87d7d58e;
})();
""".replace("<no hooks>", "    ")

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
    '    (jsx("button", ({className:"p-8",style:({ ["color"] : "black", '
    '["opacity"] : 0.5, ["paddingTop"] : "4px", ["paddingRight"] : "4px", '
    '["paddingBottom"] : "4px", ["paddingLeft"] : "4px", ["zIndex"] : 2 })}), '
    '"hello"))\n'
    "  )\n"
    "}"
)


class Plain(UIComponent):
    """An element with no look of its own."""


class Card(UIComponent):
    """An element whose look has a condition."""

    tag = "section"

    styles: ClassVar[ComponentStyles] = {
        "base": {"color": {"default": "red", ":hover": "blue"}, "top": "8px"},
    }


class Button(UIComponent):
    """An element with variants, a layout prop and an attribute."""

    tag = "button"

    styles: ClassVar[ComponentStyles] = {
        "base": {"color": "black"},
        "variants": {
            "kind": {
                "solid": {"color": "white", "background_color": "black"},
                "soft": {"opacity": 0.5},
            },
            "size": {"1": {"height": "1em"}, "2": {"height": "2em"}},
        },
        "compound": [
            {"props": {"kind": "solid", "size": "2"}, "style": {"font_weight": 700}},
        ],
    }

    # Which look the button has.
    kind: Var[Literal["solid", "soft"]]

    # How tall the button is.
    size: Var[Literal["1", "2"]]

    # The space between the children.
    gap: Var[str]

    # The tooltip of the element.
    title: Var[str]


class Switch(UIComponent):
    """An element with an inner element that the same props style."""

    tag = "button"

    styles: ClassVar[ComponentStyles] = {
        "base": {"width": "2em"},
        "parts": {
            "track": {"base": {"display": "block"}},
            "thumb": {
                "base": {"width": "1em"},
                "variants": {"size": {"2": {"width": "2em"}}},
            },
        },
    }

    # How large the switch is.
    size: Var[Literal["1", "2"]]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the switch around its track and thumb.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The component.
        """
        return super().create(
            Part.create(
                Part.create(part="thumb", tag="span"), part="track", tag="span"
            ),
            *children,
            **props,
        )


class BaseTestState(rx.State):
    """State the styles, the props and the class names are bound to."""

    color: rx.Field[str] = rx.field("red")
    names: rx.Field[str] = rx.field("p-8")
    kind: rx.Field[str] = rx.field("solid")
    size: rx.Field[str] = rx.field("1")
    styles: rx.Field[dict[str, str]] = rx.field(default_factory=dict)

    @rx.event
    def noop(self):
        """Do nothing."""


S = BaseTestState

# Styles a type checker refuses, typed loosely to reach the compiler.
MISSPELT: Any = {"paddng": "1em"}
NESTED: Any = {"& > div": {"color": "red"}}
NOT_A_STYLE: Any = ["color: red"]


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
    assert component._get_all_imports() == {}


def test_style_is_spread_from_a_declaration_and_never_a_css_prop(ui_plugin: UIPlugin):
    """The user's style is merged over the component's, by property."""
    component = Card.create("hello", style={"top": "4px", "margin_top": 2})
    assert component._get_all_custom_code() == {
        'const sx_14c89d843a = stylex.create({ s: {"color": {"default": "red", '
        '":hover": "blue"}, "top": "4px", "marginTop": 2} });\n'
        "const sx_14c89d843a_c = stylex.props(sx_14c89d843a.s).className;": None
    }
    assert component.render() == {
        "name": '"section"',
        "props": ["className:sx_14c89d843a_c"],
        "children": [{"contents": '"hello"'}],
    }
    assert component._get_style() == {}


def test_keyword_arguments_are_props_events_attributes_or_styles(ui_plugin: UIPlugin):
    """Only what is none of the first three is read as a CSS property.

    A prop the style table reads and a layout prop are styles too: neither is
    an attribute of the element.
    """
    component = Button.create(
        "save",
        kind="solid",
        size="2",
        gap="3",
        title="Save",
        id="save",
        data_state="on",
        aria_label="Save",
        on_click=S.noop,
        margin_top="1px",
        style={"margin_top": "2px", "top": 0},
    )
    assert component._get_all_custom_code() == {
        'const sx_1027767e47 = stylex.create({ s: {"color": "white", '
        '"backgroundColor": "black", "height": "2em", "fontWeight": 700, "rowGap": '
        '"var(--space-3)", "columnGap": "var(--space-3)", "top": 0, "marginTop": '
        '"1px"} });\n'
        "const sx_1027767e47_c = stylex.props(sx_1027767e47.s).className;": None
    }
    assert component.render()["props"] == [
        '"aria-label":"Save"',
        "className:sx_1027767e47_c",
        '"data-state":"on"',
        'id:"save"',
        (
            'onClick:((_e) => (addEvents([(ReflexEvent("reflex___state____state.'
            'tests___units___reflex_components_ui___test_base____base_test_state.noop", '
            "({  }), ({  })))], [_e], ({  }))))"
        ),
        "ref:ref_save",
        'title:"Save"',
    ]
    assert list(component.event_triggers) == ["on_click"]
    assert component.style == {}


@pytest.mark.parametrize(
    ("create", "message"),
    [
        (
            lambda: Card.create(paddng="1em"),
            'rx.ui.card: unknown CSS property "paddng". Did you mean "padding"?',
        ),
        (
            lambda: Card.create(style=MISSPELT),
            'rx.ui.card: unknown CSS property "paddng". Did you mean "padding"?',
        ),
        (
            lambda: Card.create(style=NESTED),
            (
                'rx.ui.card: style key "& > div" is a nested selector, which rx.ui '
                "styles do not support. Style the child component directly, or keep "
                "rx.card for this element."
            ),
        ),
        (
            # A layout prop of another component is not one of this one.
            lambda: Card.create(spacing="3"),
            'rx.ui.card: unknown CSS property "spacing". Did you mean "padding"?',
        ),
        (
            lambda: Card.create(style=NOT_A_STYLE),
            (
                "rx.ui.card: style must be a dict of styles, a list of them or a "
                "Var, not str."
            ),
        ),
        (
            lambda: Button.create(gap=S.color),
            (
                'rx.ui.button: layout prop "gap" is bound to state, but its values '
                'are read at compile time. Bind the "gap" style instead, which takes '
                "any CSS value."
            ),
        ),
        (
            lambda: Card.create(background=S.color),
            (
                'rx.ui.card: style "background" is bound to state, but rx.ui styles '
                "split this shorthand into longhands at compile time. Bind "
                "background_color, background_image and its other longhands instead."
            ),
        ),
    ],
)
def test_style_that_cannot_be_compiled_is_an_error_where_it_is_written(
    create: Callable[[], UIComponent], message: str
):
    with pytest.raises(StyleError) as raised:
        create()
    assert str(raised.value) == message


def test_unknown_event_trigger_is_not_mistaken_for_a_style():
    with pytest.raises(ValueError) as raised:
        Plain.create(on_paddng=S.noop)
    assert str(raised.value) == (
        "The Plain does not take in an `on_paddng` event trigger. Valid triggers "
        "for Plain: ['on_blur', 'on_click', 'on_context_menu', 'on_double_click', "
        "'on_focus', 'on_mount', 'on_mouse_down', 'on_mouse_enter', "
        "'on_mouse_leave', 'on_mouse_move', 'on_mouse_out', 'on_mouse_over', "
        "'on_mouse_up', 'on_scroll', 'on_scroll_end', 'on_unmount']. If Plain is a "
        "third party component make sure to add `on_paddng` to the component's "
        "event triggers. visit "
        "https://reflex.dev/docs/wrapping-react/guide/#event-triggers for more info."
    )


def test_styles_in_a_list_and_keywords_are_written_over_each_other(
    ui_plugin: UIPlugin,
):
    """A key replaces the same key, as in the style of any Reflex component.

    What is written last wins over a shorthand or a longhand written before
    it, and a keyword argument is written after the ``style``.
    """
    component = Plain.create(
        style=[
            {"padding_top": "1px", "_hover": {"color": "red"}},
            {"padding": "2px", "_hover": {"opacity": 0.5}},
            {"padding_top": "3px"},
        ],
        color="blue",
    )
    assert component._get_all_custom_code() == {
        'const sx_1799fc9438 = stylex.create({ s: {"paddingTop": "3px", '
        '"paddingRight": "2px", "paddingBottom": "2px", "paddingLeft": "2px", '
        '"opacity": {":hover": 0.5}, "color": "blue"} });\n'
        "const sx_1799fc9438_c = stylex.props(sx_1799fc9438.s).className;": None
    }


def test_style_per_breakpoint_becomes_blocks_under_media_queries(ui_plugin: UIPlugin):
    named = Plain.create(
        style=rx.breakpoints(initial={"color": "red", "top": 0}, sm={"color": "blue"})
    )
    assert named._get_all_custom_code() == {
        'const sx_10c4c20799 = stylex.create({ s: {"color": {"default": "red", '
        '"@media screen and (min-width: 48em)": "blue"}, "top": 0} });\n'
        "const sx_10c4c20799_c = stylex.props(sx_10c4c20799.s).className;": None
    }
    custom = Plain.create(style=rx.breakpoints({"0px": {"top": 0}, "40em": {"top": 1}}))
    assert custom._get_all_custom_code() == {
        'const sx_8b8c48b483 = stylex.create({ s: {"top": {"@media screen and '
        '(min-width: 0px)": 0, "@media screen and (min-width: 40em)": 1}} });\n'
        "const sx_8b8c48b483_c = stylex.props(sx_8b8c48b483.s).className;": None
    }


def test_literal_class_names_are_joined_with_those_of_the_style(ui_plugin: UIPlugin):
    """The element has one className: its own class names, then the constant."""
    component = Card.create(class_name=["p-8", "m-2"], custom_attrs={"role": "note"})
    assert component.render()["props"] == [
        'className:"p-8 m-2 " + sx_262fdfab15_c',
        'role:"note"',
    ]


def test_class_names_from_state_are_joined_with_those_of_the_style(ui_plugin: UIPlugin):
    component = Card.create(class_name=S.names)
    assert component.render()["props"] == [
        f'className:({S.names!s}) + " " + sx_262fdfab15_c'
    ]


def test_value_bound_to_state_is_a_custom_property_of_the_element(ui_plugin: UIPlugin):
    component = Card.create(width=S.color, class_name="p-8", style=S.styles)
    assert component._get_all_custom_code() == {
        'const sx_bf234bb6b2 = stylex.create({ s: {"color": {"default": "red", '
        '":hover": "blue"}, "top": "8px", "width": "var(--v0)"} });\n'
        "const sx_bf234bb6b2_c = stylex.props(sx_bf234bb6b2.s).className;": None
    }
    assert component.render()["props"] == [
        'className:"p-8 " + sx_bf234bb6b2_c',
        f'style:({{ "--v0": ({S.color!s}) ?? "initial", ...{S.styles!s} }})',
    ]
    # The Vars bring the hooks that read the state into the module.
    assert [str(var) for var in component._get_vars()] == [
        str(S.color),
        str(S.styles),
    ]


def test_whole_style_from_state_is_the_inline_style(ui_plugin: UIPlugin):
    component = Plain.create(style=S.styles)
    assert component._get_all_custom_code() == {}
    assert component.render()["props"] == [f"style:{S.styles!s}"]


# The styles of each value of the button's kind, and of a value that is none.
KIND_DECLARATION = (
    'const sx_749372103b = stylex.create({ a0_0: {"color": "white", '
    '"backgroundColor": "black"}, a0_1: {"color": "black", "opacity": 0.5}, a0: '
    '{"color": "black"} });\n'
    'const sx_749372103b_0 = { __proto__: null, "solid": '
    'stylex.props(sx_749372103b.a0_0).className, "soft": '
    "stylex.props(sx_749372103b.a0_1).className };\n"
    "const sx_749372103b_0d = stylex.props(sx_749372103b.a0).className;"
)
KIND_LOOKUP = "(sx_749372103b_0[<kind>] ?? sx_749372103b_0d)"


@pytest.mark.parametrize(
    ("props", "declaration", "rendered"),
    [
        ({"kind": S.kind}, KIND_DECLARATION, [f"className:{KIND_LOOKUP}"]),
        (
            {"kind": S.kind, "class_name": "p-8"},
            KIND_DECLARATION,
            [f'className:"p-8 " + {KIND_LOOKUP}'],
        ),
        (
            {"kind": S.kind, "class_name": S.names},
            KIND_DECLARATION,
            [f'className:(<names>) + " " + {KIND_LOOKUP}'],
        ),
        (
            # Props that a compound style combines are indexed together.
            {"kind": S.kind, "size": S.size},
            (
                'const sx_5874f5ad04 = stylex.create({ a0_0: {"color": "white", '
                '"backgroundColor": "black", "height": "1em"}, a0_1: {"color": '
                '"white", "backgroundColor": "black", "height": "2em", "fontWeight": '
                '700}, a0_2: {"color": "black", "opacity": 0.5, "height": "1em"}, '
                'a0_3: {"color": "black", "opacity": 0.5, "height": "2em"}, a0: '
                '{"color": "black"} });\n'
                'const sx_5874f5ad04_0 = { __proto__: null, "solid": { __proto__: '
                'null, "1": stylex.props(sx_5874f5ad04.a0_0).className, "2": '
                'stylex.props(sx_5874f5ad04.a0_1).className }, "soft": { __proto__: '
                'null, "1": stylex.props(sx_5874f5ad04.a0_2).className, "2": '
                "stylex.props(sx_5874f5ad04.a0_3).className } };\n"
                "const sx_5874f5ad04_0d = stylex.props(sx_5874f5ad04.a0).className;"
            ),
            ["className:(sx_5874f5ad04_0[<kind>]?.[<size>] ?? sx_5874f5ad04_0d)"],
        ),
    ],
)
def test_prop_bound_to_state_indexes_the_class_names_of_its_values(
    ui_plugin: UIPlugin, props: dict[str, Any], declaration: str, rendered: list[str]
):
    component = Button.create(**props)
    assert component._get_all_custom_code() == {declaration: None}
    assert component.render()["props"] == [
        prop
        .replace("<kind>", str(S.kind))
        .replace("<size>", str(S.size))
        .replace("<names>", str(S.names))
        for prop in rendered
    ]


def test_parts_are_styled_by_the_table_of_their_component(ui_plugin: UIPlugin):
    """A part reads the props of its component, bound to state or not."""
    width = (
        'const sx_95ab4202b0 = stylex.create({ s: {"width": "2em"} });\n'
        "const sx_95ab4202b0_c = stylex.props(sx_95ab4202b0.s).className;"
    )
    block = (
        'const sx_1cb1fb1245 = stylex.create({ s: {"display": "block"} });\n'
        "const sx_1cb1fb1245_c = stylex.props(sx_1cb1fb1245.s).className;"
    )
    component = Switch.create("on", size="2")
    # The switch and its thumb have the same style, and share its declaration.
    assert component._get_all_custom_code() == {width: None, block: None}
    assert component.render() == {
        "name": '"button"',
        "props": ["className:sx_95ab4202b0_c"],
        "children": [
            {
                "name": '"span"',
                "props": ["className:sx_1cb1fb1245_c"],
                "children": [
                    {
                        "name": '"span"',
                        "props": ["className:sx_95ab4202b0_c"],
                        "children": [],
                    }
                ],
            },
            {"contents": '"on"'},
        ],
    }
    bound = Switch.create(size=S.size)
    assert bound._get_all_custom_code() == {
        width: None,
        block: None,
        (
            'const sx_bd2235d0fb = stylex.create({ a0_0: {"width": "2em"}, a0: '
            '{"width": "1em"} });\n'
            'const sx_bd2235d0fb_0 = { __proto__: null, "2": '
            "stylex.props(sx_bd2235d0fb.a0_0).className };\n"
            "const sx_bd2235d0fb_0d = stylex.props(sx_bd2235d0fb.a0).className;"
        ): None,
    }
    thumb = bound.render()["children"][0]["children"][0]
    assert thumb == {
        "name": '"span"',
        "props": [f"className:(sx_bd2235d0fb_0[{S.size!s}] ?? sx_bd2235d0fb_0d)"],
        "children": [],
    }
    # The size is a style of the switch and its thumb, not an attribute.
    assert bound.render()["props"] == ["className:sx_95ab4202b0_c"]


def test_part_outside_its_component_says_where_it_belongs(ui_plugin: UIPlugin):
    with pytest.raises(StyleError) as raised:
        Switch.create(Part.create(part="thum"))
    assert str(raised.value) == (
        'rx.ui.switch: its style table has no part "thum". Did you mean "thumb"?'
    )
    with pytest.raises(StyleError) as raised:
        Part.create(part="thumb", color="red")
    assert str(raised.value) == (
        'rx.ui.part: the part "thumb" takes its styles from the style table of its '
        "component. Style it there."
    )
    stray = Plain.create(Part.create(part="thumb"))
    message = (
        'rx.ui.part: the part "thumb" is not in a component whose style table has '
        "it. Create it as a child of its component, or of another part of it."
    )
    with pytest.raises(StyleError) as raised:
        stray.render()
    assert str(raised.value) == message
    # The same holds where the component is evaluated in the browser.
    with pytest.raises(StyleError) as raised:
        serialize(stray)
    assert str(raised.value) == message


def test_styles_of_the_app_apply_before_those_of_the_element(ui_plugin: UIPlugin):
    component = Card.create(top="1px")
    component._add_style_recursive({
        Card: rx.Style({"top": "2px", "color": "green", "_hover": {"left": 0}})
    })
    assert component._get_all_custom_code() == {
        'const sx_802fe7deea = stylex.create({ s: {"color": "green", "top": "1px", '
        '"left": {":hover": 0}} });\n'
        "const sx_802fe7deea_c = stylex.props(sx_802fe7deea.s).className;": None
    }


def test_page_declares_styles_and_imports_the_modules_of_their_tokens(
    ui_plugin: UIPlugin, compile_page: Callable[..., CompileContext]
):
    def page():
        return rx.el.main(
            Card.create("ruby", color=rx.color("ruby", 9)),
            Card.create("again", color=rx.color("ruby", 9)),
            Plain.create("jade", background_color=rx.color("jade", 3)),
        )

    assert compile_page(page).compiled_pages["/"].output_code == PAGE


def test_declaration_and_imports_follow_the_element_into_a_memo_module(
    ui_plugin: UIPlugin, compile_page: Callable[..., CompileContext]
):
    """StyleX only folds a style declared in the module that renders it.

    A value bound to state makes the compiler move the element into a module
    of its own: the declaration and the imports go there, and leave the page.
    """
    ctx = compile_page(
        lambda: Button.create(
            "hello",
            kind=S.kind,
            width=S.color,
            border_top_color=rx.color("ruby", 9),
        )
    )
    assert ctx.compiled_pages["/"].output_code == MEMO_PAGE
    ((_, memo_module),) = compiler.compile_memo_components(
        tuple(ctx.auto_memo_components.values())
    )[0]
    assert memo_module == MEMO_MODULE


def test_declaration_and_imports_follow_the_element_into_an_rx_memo_module(
    ui_plugin: UIPlugin, preserve_memo_registries: None
):
    @rx.memo
    def ruby_card() -> rx.Component:
        return Card.create("ruby", color=rx.color("ruby", 9))

    ((_, memo_module),) = compiler.compile_memo_components((
        next(memo for memo in MEMOS.values() if memo.python_name == "ruby_card"),
    ))[0]
    assert memo_module == RX_MEMO_MODULE


def test_dynamic_component_falls_back_to_an_inline_style():
    """Code evaluated in the browser has no build, no plugin and no StyleX."""
    component = Button.create(
        "hello", kind="soft", style={"padding": "4px", "z_index": 2}, class_name="p-8"
    )
    assert serialize(component) == DYNAMIC_MODULE


@pytest.mark.parametrize(
    ("create", "message"),
    [
        (
            lambda: Card.create("hello"),
            (
                'rx.ui.card: the style "color" has conditions ("default", ":hover"), '
                "which a component rendered from state cannot apply: its code is "
                "evaluated in the browser and never reaches the StyleX compiler. Use an "
                "unconditional value there, or render the component in a page and show "
                "it with rx.cond."
            ),
        ),
        (
            lambda: Plain.create(width=S.color),
            (
                'rx.ui.plain: the style "width" is bound to state, which a component '
                "rendered from state cannot apply: its code is evaluated in the browser "
                "and never reaches the StyleX compiler. Use a literal value there, or "
                "render the component in a page and show it with rx.cond."
            ),
        ),
        (
            lambda: Button.create(kind=S.kind),
            (
                'rx.ui.button: the props "kind" select a style and are bound to '
                "state, which a component rendered from state cannot apply: its code is "
                "evaluated in the browser and never reaches the StyleX compiler. Give "
                "them literal values there, or render the component in a page and show "
                "it with rx.cond."
            ),
        ),
    ],
)
def test_dynamic_component_cannot_have_a_style_that_needs_the_compiler(
    create: Callable[[], UIComponent], message: str
):
    with pytest.raises(StyleError) as raised:
        serialize(create())
    assert str(raised.value) == message


class Chip(UIComponent):
    """An element with a color of its own."""

    tag = "span"

    styles: ClassVar[ComponentStyles] = {
        "base": {"background_color": tokens.accent[9], "color": tokens.accent.contrast},
    }

    # The accent color of the element.
    color_scheme: Var[LiteralAccentColor]


CHIP_PAGE = """import * as stylex from "@stylexjs/stylex"
import "$/reflex-ui/tokens/accent.stylex.js"
import {className as reflexUIClassName} from "$/reflex-ui/class-name.js"
import {accentRed} from "$/reflex-ui/themes/accent/red.js"
import {focusScope} from "$/reflex-ui/themes/focus.js"
import {useRegisteredRef} from "$/utils/state"
import {accentGray} from "$/reflex-ui/themes/accent/gray.js"
import {Chip_span_a1f191971c1d0b090104807deb864e69} from "$/utils/components/Chip_span_a1f191971c1d0b090104807deb864e69"
import {Fragment,useEffect} from "react"
import {jsx} from "@emotion/react"



const sx_8f99169642 = stylex.create({ s: {"backgroundColor": "var(--accent-9)", "color": "var(--accent-contrast)"} });
const sx_8f99169642_c = stylex.props(sx_8f99169642.s).className;
const reflexUIClasses_01ac7ed29f = reflexUIClassName(accentRed, focusScope);
const reflexUIClasses_fe8edd03f8 = reflexUIClassName(accentGray);

function Component() {
const ref_gray = useRegisteredRef("ref_gray");

  return (
    jsx(Fragment,{},jsx("main",{},jsx("span",{className:sx_8f99169642_c},"theme"),jsx("span",{className:"p-8 " + sx_8f99169642_c + " " + reflexUIClasses_01ac7ed29f},"red"),jsx("span",{className:sx_8f99169642_c + " " + reflexUIClasses_01ac7ed29f},"red again"),jsx("span",{className:sx_8f99169642_c + " " + reflexUIClasses_fe8edd03f8,id:"gray",ref:ref_gray},"gray"),jsx(Chip_span_a1f191971c1d0b090104807deb864e69,{},"bound")),jsx("title",{}," | Index"),jsx("meta",{content:"",property:"og:image"},))
  )
}
Component.displayName = "Component(/)";

export default Component;
"""

BOUND_CHIP = """
import {isTrue,mergeSlotProps} from "$/utils/state"
import {useStateContext} from "$/utils/context-registry"
import * as stylex from "@stylexjs/stylex"
import "$/reflex-ui/tokens/accent.stylex.js"
import {className as reflexUIClassName} from "$/reflex-ui/class-name.js"
import {accentAmber} from "$/reflex-ui/themes/accent/amber.js"
import {accentBlue} from "$/reflex-ui/themes/accent/blue.js"
import {accentBronze} from "$/reflex-ui/themes/accent/bronze.js"
import {accentBrown} from "$/reflex-ui/themes/accent/brown.js"
import {accentCrimson} from "$/reflex-ui/themes/accent/crimson.js"
import {accentCyan} from "$/reflex-ui/themes/accent/cyan.js"
import {accentGold} from "$/reflex-ui/themes/accent/gold.js"
import {accentGrass} from "$/reflex-ui/themes/accent/grass.js"
import {accentGray} from "$/reflex-ui/themes/accent/gray.js"
import {accentGreen} from "$/reflex-ui/themes/accent/green.js"
import {accentIndigo} from "$/reflex-ui/themes/accent/indigo.js"
import {accentIris} from "$/reflex-ui/themes/accent/iris.js"
import {accentJade} from "$/reflex-ui/themes/accent/jade.js"
import {accentLime} from "$/reflex-ui/themes/accent/lime.js"
import {accentMint} from "$/reflex-ui/themes/accent/mint.js"
import {accentOrange} from "$/reflex-ui/themes/accent/orange.js"
import {accentPink} from "$/reflex-ui/themes/accent/pink.js"
import {accentPlum} from "$/reflex-ui/themes/accent/plum.js"
import {accentPurple} from "$/reflex-ui/themes/accent/purple.js"
import {accentRed} from "$/reflex-ui/themes/accent/red.js"
import {accentRuby} from "$/reflex-ui/themes/accent/ruby.js"
import {accentSky} from "$/reflex-ui/themes/accent/sky.js"
import {accentTeal} from "$/reflex-ui/themes/accent/teal.js"
import {accentTomato} from "$/reflex-ui/themes/accent/tomato.js"
import {accentViolet} from "$/reflex-ui/themes/accent/violet.js"
import {accentYellow} from "$/reflex-ui/themes/accent/yellow.js"
import {focusScope} from "$/reflex-ui/themes/focus.js"
import {jsx} from "@emotion/react"
import {Fragment,memo,useEffect} from "react"



const sx_8f99169642 = stylex.create({ s: {"backgroundColor": "var(--accent-9)", "color": "var(--accent-contrast)"} });
const sx_8f99169642_c = stylex.props(sx_8f99169642.s).className;
const reflexUIColorSchemes = { __proto__: null, "amber": reflexUIClassName(accentAmber, focusScope), "blue": reflexUIClassName(accentBlue, focusScope), "bronze": reflexUIClassName(accentBronze, focusScope), "brown": reflexUIClassName(accentBrown, focusScope), "crimson": reflexUIClassName(accentCrimson, focusScope), "cyan": reflexUIClassName(accentCyan, focusScope), "gold": reflexUIClassName(accentGold, focusScope), "grass": reflexUIClassName(accentGrass, focusScope), "gray": reflexUIClassName(accentGray), "green": reflexUIClassName(accentGreen, focusScope), "indigo": reflexUIClassName(accentIndigo, focusScope), "iris": reflexUIClassName(accentIris, focusScope), "jade": reflexUIClassName(accentJade, focusScope), "lime": reflexUIClassName(accentLime, focusScope), "mint": reflexUIClassName(accentMint, focusScope), "orange": reflexUIClassName(accentOrange, focusScope), "pink": reflexUIClassName(accentPink, focusScope), "plum": reflexUIClassName(accentPlum, focusScope), "purple": reflexUIClassName(accentPurple, focusScope), "red": reflexUIClassName(accentRed, focusScope), "ruby": reflexUIClassName(accentRuby, focusScope), "sky": reflexUIClassName(accentSky, focusScope), "teal": reflexUIClassName(accentTeal, focusScope), "tomato": reflexUIClassName(accentTomato, focusScope), "violet": reflexUIClassName(accentViolet, focusScope), "yellow": reflexUIClassName(accentYellow, focusScope) };


export const Chip_span_a1f191971c1d0b090104807deb864e69 = /*#__PURE__*/ (() => {
const Chip_span_a1f191971c1d0b090104807deb864e69 = memo(({children, ...rest}) => {
    const reflex___state____state__tests___units___reflex_components_ui___test_base____base_test_state = useStateContext("reflex___state____state.tests___units___reflex_components_ui___test_base____base_test_state", ["color_rx_state_"])
    return(
        jsx("span",{...mergeSlotProps(rest, ({ className:sx_8f99169642_c + " " + reflexUIColorSchemes[reflex___state____state__tests___units___reflex_components_ui___test_base____base_test_state.color_rx_state_] }))},children)
    )
});
Chip_span_a1f191971c1d0b090104807deb864e69.displayName = "Chip";
return Chip_span_a1f191971c1d0b090104807deb864e69;
})();
"""


def test_color_scheme_is_the_accent_of_the_element(
    ui_plugin: UIPlugin, compile_page: Callable[..., CompileContext]
):
    """A literal color imports its accent; one bound to state imports them all."""

    def page():
        return rx.el.main(
            Chip.create("theme"),
            Chip.create("red", color_scheme="red", class_name="p-8"),
            Chip.create("red again", color_scheme="red"),
            Chip.create("gray", color_scheme="gray", id="gray"),
            Chip.create("bound", color_scheme=S.color),  # pyright: ignore [reportArgumentType]
        )

    ctx = compile_page(page)
    assert ctx.compiled_pages["/"].output_code == CHIP_PAGE
    files, _ = compiler.compile_memo_components(ctx.auto_memo_components.values())
    assert [code for path, code in files if "Chip_span_" in path] == [BOUND_CHIP]


def test_color_scheme_must_be_an_accent_color():
    with pytest.raises(ThemeError) as raised:
        Chip.create("hello", color_scheme="slate")  # pyright: ignore [reportArgumentType]
    assert str(raised.value) == (
        'rx.ui.chip: unknown color_scheme "slate". The values are "tomato", '
        '"red", "ruby", "crimson", "pink", "plum", "purple", "violet", "iris", '
        '"indigo", "blue", "cyan", "teal", "jade", "green", "grass", "brown", '
        '"orange", "sky", "mint", "lime", "yellow", "amber", "gold", "bronze", '
        '"gray".'
    )


def test_color_scheme_is_a_css_property_of_a_component_without_the_prop(
    ui_plugin: UIPlugin,
):
    """Only a component that declares the prop reads it as an accent."""
    component = Plain.create("hello", color_scheme="dark")
    assert component._get_all_custom_code() == {
        'const sx_b7c693ea0b = stylex.create({ s: {"colorScheme": "dark"} });\n'
        "const sx_b7c693ea0b_c = stylex.props(sx_b7c693ea0b.s).className;": None
    }


def test_dynamic_component_cannot_have_a_color_scheme():
    with pytest.raises(StyleError) as raised:
        serialize(Chip.create("hello", color_scheme="red"))
    assert str(raised.value) == (
        "rx.ui.chip: color_scheme cannot be applied to a component rendered "
        "from state: its code is evaluated in the browser and never reaches "
        "the StyleX compiler. Render the component in a page and show it with "
        "rx.cond."
    )
