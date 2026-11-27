"""Tests for reflex_components_ui.layout.theme."""

from collections.abc import Callable

import pytest
from pytest_mock import MockerFixture
from reflex_base.components.component import Component
from reflex_base.config import get_config
from reflex_base.plugins import CompileContext
from reflex_base.utils.exceptions import ConfigError
from reflex_base.utils.serializers import serialize
from reflex_components_core.base.app_wrap import AppWrap
from reflex_components_ui.layout.theme import Appearance, AppTheme, ThemeElement
from reflex_components_ui.plugin import APP_THEME_WRAP, UIPlugin
from reflex_components_ui.themes import Theme, ThemeError

import reflex as rx
from reflex.compiler import compiler

APP_ROOT = (
    """
import {className as reflexUIClassName} from "$/reflex-ui/class-name.js"
import {accentIndigo} from "$/reflex-ui/themes/accent/indigo.js"
import {focusScope} from "$/reflex-ui/themes/focus.js"
import {graySlate} from "$/reflex-ui/themes/gray/slate.js"
import {panelTranslucent} from "$/reflex-ui/themes/panel.js"
import {radiusLarge} from "$/reflex-ui/themes/radius.js"
import {scaling100} from "$/reflex-ui/themes/scaling.js"
import {colorScope,radiusScope,shadowScope,spaceScope,typographyScope} from "$/reflex-ui/themes/scope.js"
import {theme as reflexUITheme} from "$/reflex-ui/themes/theme.js"
import * as stylex from "@stylexjs/stylex"
import {Fragment,useEffect} from "react"
import {jsx} from "@emotion/react"

import { defaultColorMode } from "$/utils/context";
import { ThemeProvider } from '$/utils/react-theme';
import { Layout as AppLayout } from './_document';
import { Outlet } from 'react-router';



const sx_c1c0436182 = stylex.create({ s: {"position": "relative", "zIndex": 0, "minHeight": {"default": "100vh", "@supports (min-height: 100dvh)": "100dvh"}} });
const sx_c1c0436182_c = stylex.props(sx_c1c0436182.s).className;
const sx_c1c0436182_o = sx_c1c0436182.s;
const reflexUIClasses_48dbd5f3d5 = "reflex-ui-theme " + reflexUIClassName(spaceScope, radiusScope, typographyScope, shadowScope, colorScope, focusScope, accentIndigo, graySlate, radiusLarge, scaling100, panelTranslucent, reflexUITheme.root, reflexUITheme.background, sx_c1c0436182_o);

function ReflexProviders({children}) {
  useEffect(() => {
    // Make contexts and state objects available globally for dynamic eval'd components
    window.__reflex = {
"""
    # The template indents the libraries of the app, of which there are none.
    "      \n"
    """    };
  }, []);

  return jsx(ThemeProvider, {defaultTheme: defaultColorMode, attribute: "class"},
    jsx(AppWrap, {}, children)
  );
}


function AppWrap({children}) {

return (jsx("div",{className:reflexUIClasses_48dbd5f3d5},jsx(Fragment,{},children)))
}

export function Layout({children}) {
  return jsx(AppLayout, {}, jsx(ReflexProviders, {}, children));
}

// Used by entry.client.js when mount_target is configured: skips the document
// shell (which renders react-router's <Meta>/<Scripts>/<Links> and requires a
// framework router context) but keeps the runtime providers.
export function EmbedLayout({children}) {
  return jsx(ReflexProviders, {}, children);
}

export default function App() {
  return jsx(Outlet, {});
}

"""
)

NESTED_PAGE = """import * as stylex from "@stylexjs/stylex"
import "$/reflex-ui/tokens/accent.stylex.js"
import {className as reflexUIClassName} from "$/reflex-ui/class-name.js"
import {accentRed} from "$/reflex-ui/themes/accent/red.js"
import {focusScope} from "$/reflex-ui/themes/focus.js"
import {colorScope,radiusScope,shadowScope,spaceScope,typographyScope} from "$/reflex-ui/themes/scope.js"
import {theme as reflexUITheme} from "$/reflex-ui/themes/theme.js"
import {useRegisteredRef} from "$/utils/state"
import {radiusFull} from "$/reflex-ui/themes/radius.js"
import {Fragment,useEffect} from "react"
import {jsx} from "@emotion/react"



const sx_e0e666cdfc = stylex.create({ s: {"boxSizing": "border-box", "display": "block", "color": "var(--accent-9)"} });
const sx_e0e666cdfc_c = stylex.props(sx_e0e666cdfc.s).className;
const reflexUIClasses_22039616de = "reflex-ui-theme " + reflexUIClassName(spaceScope, radiusScope, typographyScope, shadowScope, colorScope, focusScope, accentRed, reflexUITheme.root);
const sx_2ccd5239f0 = stylex.create({ s: {"paddingTop": "4px", "paddingRight": "4px", "paddingBottom": "4px", "paddingLeft": "4px"} });
const sx_2ccd5239f0_c = stylex.props(sx_2ccd5239f0.s).className;
const sx_2ccd5239f0_o = sx_2ccd5239f0.s;
const reflexUIClasses_fd8fdcb49a = "reflex-ui-theme " + reflexUIClassName(spaceScope, radiusScope, typographyScope, shadowScope, colorScope, focusScope, radiusFull, reflexUITheme.root, reflexUITheme.background, reflexUITheme.dark, sx_2ccd5239f0_o);
const sx_71b84cd269 = stylex.create({ s: {"display": "contents"} });
const sx_71b84cd269_c = stylex.props(sx_71b84cd269.s).className;
const reflexUIClasses_7830a5bcf7 = "reflex-ui-theme " + reflexUIClassName(spaceScope, radiusScope, typographyScope, shadowScope, colorScope, focusScope, reflexUITheme.root);

function Component() {
const ref_dark = useRegisteredRef("ref_dark");

  return (
    jsx(Fragment,{},jsx("main",{},jsx("div",{className:reflexUIClasses_22039616de},jsx("div",{className:sx_e0e666cdfc_c},"red")),jsx("div",{className:"dark " + sx_71b84cd269_c},jsx("div",{className:"p-8 " + reflexUIClasses_fd8fdcb49a,id:"dark",ref:ref_dark},"dark")),jsx("div",{className:reflexUIClasses_7830a5bcf7},"plain")),jsx("title",{}," | Index"),jsx("meta",{content:"",property:"og:image"},))
  )
}
Component.displayName = "Component(/)";

export default Component;
"""

BOUND_PAGE = """import {Themeelement_div_45c9f04fbd77a86b901df8ec7c9186f5} from "$/utils/components/Themeelement_div_45c9f04fbd77a86b901df8ec7c9186f5"
import {Themeelement_div_110e113e071e5dc30028d2a466586629} from "$/utils/components/Themeelement_div_110e113e071e5dc30028d2a466586629"
import {Fragment,useEffect} from "react"
import {jsx} from "@emotion/react"





function Component() {


  return (
    jsx(Fragment,{},jsx("main",{},jsx(Themeelement_div_45c9f04fbd77a86b901df8ec7c9186f5,{},"accent"),jsx(Themeelement_div_110e113e071e5dc30028d2a466586629,{},"names")),jsx("title",{}," | Index"),jsx("meta",{content:"",property:"og:image"},))
  )
}
Component.displayName = "Component(/)";

export default Component;
"""

BOUND_ACCENT_THEME = """
import {isTrue,mergeSlotProps} from "$/utils/state"
import {useStateContext} from "$/utils/context-registry"
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
import {colorScope,radiusScope,shadowScope,spaceScope,typographyScope} from "$/reflex-ui/themes/scope.js"
import {theme as reflexUITheme} from "$/reflex-ui/themes/theme.js"
import {jsx} from "@emotion/react"
import {Fragment,memo,useEffect} from "react"



const reflexUIAccents = { __proto__: null, "amber": accentAmber, "blue": accentBlue, "bronze": accentBronze, "brown": accentBrown, "crimson": accentCrimson, "cyan": accentCyan, "gold": accentGold, "grass": accentGrass, "gray": accentGray, "green": accentGreen, "indigo": accentIndigo, "iris": accentIris, "jade": accentJade, "lime": accentLime, "mint": accentMint, "orange": accentOrange, "pink": accentPink, "plum": accentPlum, "purple": accentPurple, "red": accentRed, "ruby": accentRuby, "sky": accentSky, "teal": accentTeal, "tomato": accentTomato, "violet": accentViolet, "yellow": accentYellow };


export const Themeelement_div_45c9f04fbd77a86b901df8ec7c9186f5 = /*#__PURE__*/ (() => {
const Themeelement_div_45c9f04fbd77a86b901df8ec7c9186f5 = memo(({children, ...rest}) => {
    const reflex___state____state__tests___units___reflex_components_ui___layout___test_theme____theme_state = useStateContext("reflex___state____state.tests___units___reflex_components_ui___layout___test_theme____theme_state", ["accent_rx_state_"])
    return(
        jsx("div",{...mergeSlotProps(rest, ({ className:"reflex-ui-theme " + reflexUIClassName(spaceScope, radiusScope, typographyScope, shadowScope, colorScope, focusScope, reflexUIAccents[reflex___state____state__tests___units___reflex_components_ui___layout___test_theme____theme_state.accent_rx_state_], reflexUITheme.root) }))},children)
    )
});
Themeelement_div_45c9f04fbd77a86b901df8ec7c9186f5.displayName = "ThemeElement";
return Themeelement_div_45c9f04fbd77a86b901df8ec7c9186f5;
})();
"""

BOUND_NAMES_THEME = """
import {isTrue,mergeSlotProps} from "$/utils/state"
import {useStateContext} from "$/utils/context-registry"
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
import {graySand} from "$/reflex-ui/themes/gray/sand.js"
import {colorScope,radiusScope,shadowScope,spaceScope,typographyScope} from "$/reflex-ui/themes/scope.js"
import {theme as reflexUITheme} from "$/reflex-ui/themes/theme.js"
import {jsx} from "@emotion/react"
import {Fragment,memo,useEffect} from "react"



const reflexUIAccents = { __proto__: null, "amber": accentAmber, "blue": accentBlue, "bronze": accentBronze, "brown": accentBrown, "crimson": accentCrimson, "cyan": accentCyan, "gold": accentGold, "grass": accentGrass, "gray": accentGray, "green": accentGreen, "indigo": accentIndigo, "iris": accentIris, "jade": accentJade, "lime": accentLime, "mint": accentMint, "orange": accentOrange, "pink": accentPink, "plum": accentPlum, "purple": accentPurple, "red": accentRed, "ruby": accentRuby, "sky": accentSky, "teal": accentTeal, "tomato": accentTomato, "violet": accentViolet, "yellow": accentYellow };


export const Themeelement_div_110e113e071e5dc30028d2a466586629 = /*#__PURE__*/ (() => {
const Themeelement_div_110e113e071e5dc30028d2a466586629 = memo(({children, ...rest}) => {
    const reflex___state____state__tests___units___reflex_components_ui___layout___test_theme____theme_state = useStateContext("reflex___state____state.tests___units___reflex_components_ui___layout___test_theme____theme_state", ["names_rx_state_", "accent_rx_state_"])
    return(
        jsx("div",{...mergeSlotProps(rest, ({ className:(reflex___state____state__tests___units___reflex_components_ui___layout___test_theme____theme_state.names_rx_state_) + " " + "reflex-ui-theme " + reflexUIClassName(spaceScope, radiusScope, typographyScope, shadowScope, colorScope, focusScope, reflexUIAccents[reflex___state____state__tests___units___reflex_components_ui___layout___test_theme____theme_state.accent_rx_state_], graySand, reflexUITheme.root) }))},children)
    )
});
Themeelement_div_110e113e071e5dc30028d2a466586629.displayName = "ThemeElement";
return Themeelement_div_110e113e071e5dc30028d2a466586629;
})();
"""


class ThemeState(rx.State):
    """State whose fields are bound to a theme."""

    accent: str = "red"
    names: str = "wide"
    appearance: str = "dark"


@pytest.fixture
def indigo_plugin(monkeypatch: pytest.MonkeyPatch) -> UIPlugin:
    """Configure the plugin with a theme, as an app does in its rxconfig.py.

    Args:
        monkeypatch: The pytest fixture that undoes the change.

    Returns:
        The configured plugin.
    """
    plugin = UIPlugin(theme=Theme(accent_color="indigo", radius="large"))
    monkeypatch.setattr(get_config(), "plugins", [plugin])
    return plugin


def test_app_root_source(monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture):
    """The element around the app names one accent, one gray and the options."""
    # The libraries a dynamic component may load are no part of the theme.
    mocker.patch(
        "reflex.compiler.compiler._split_window_libraries", return_value=([], [])
    )
    app = rx.App(enable_state=False)
    plugin = UIPlugin(theme=Theme(accent_color="indigo", radius="large"))
    monkeypatch.setattr(get_config(), "plugins", [plugin])
    root = app._app_root({
        (0, "AppWrap"): AppWrap.create(),
        APP_THEME_WRAP: AppTheme.create(),
    })
    assert compiler._compile_app(root, dynamic_components=False) == APP_ROOT


def test_plugin_wraps_an_app_with_an_appearance_in_its_class(
    monkeypatch: pytest.MonkeyPatch, compile_page: Callable[..., CompileContext]
):
    """The class of the appearance is on an element around the theme element."""
    plugin = UIPlugin(theme=Theme(appearance="dark"))
    monkeypatch.setattr(get_config(), "plugins", [plugin])
    wraps = compile_page(lambda: rx.el.main("hello"), plugin).app_wrap_components
    assert {key: type(wrap) for key, wrap in wraps.items()} == {
        (15, "ReflexUITheme"): AppTheme,
        (16, "ReflexUIAppearance"): Appearance,
    }
    assert wraps[16, "ReflexUIAppearance"].render() == {
        "name": '"div"',
        "props": ['className:"dark " + sx_71b84cd269_c'],
        "children": [],
    }
    theme = wraps[15, "ReflexUITheme"]
    assert theme.render() == {
        "name": '"div"',
        "props": ["className:reflexUIClasses_ac4861b877"],
        "children": [],
    }
    assert theme._get_all_custom_code() == {
        'const sx_c1c0436182 = stylex.create({ s: {"position": "relative", '
        '"zIndex": 0, "minHeight": {"default": "100vh", "@supports '
        '(min-height: 100dvh)": "100dvh"}} });\n'
        "const sx_c1c0436182_c = stylex.props(sx_c1c0436182.s).className;": None,
        "const sx_c1c0436182_o = sx_c1c0436182.s;": None,
        'const reflexUIClasses_ac4861b877 = "reflex-ui-theme " + '
        "reflexUIClassName(spaceScope, radiusScope, typographyScope, "
        "shadowScope, colorScope, focusScope, accentBlue, graySlate, "
        "radiusMedium, scaling100, panelTranslucent, reflexUITheme.root, "
        "reflexUITheme.background, reflexUITheme.dark, sx_c1c0436182_o);": None,
    }


def test_theme_with_an_appearance_is_inside_the_element_of_its_class(
    indigo_plugin: UIPlugin,
):
    """Only a theme with an appearance of its own has the element around it."""
    assert type(rx.ui.theme("hello")) is ThemeElement
    assert type(rx.ui.theme("hello", appearance="inherit")) is ThemeElement
    dark: Component = rx.ui.theme("hello", appearance="dark", id="dark")
    assert [type(dark), *map(type, dark.children)] == [Appearance, ThemeElement]
    bound: Component = rx.ui.theme(
        "hello",
        appearance=ThemeState.appearance,  # pyright: ignore [reportArgumentType]
    )
    assert bound.render()["props"] == [
        f'className:({ThemeState.appearance!s}) + " " + sx_71b84cd269_c'
    ]
    assert bound.children[0].render()["props"] == [
        (
            'className:"reflex-ui-theme " + reflexUIClassName(spaceScope, '
            "radiusScope, typographyScope, shadowScope, colorScope, focusScope, "
            f'reflexUITheme.root, ({ThemeState.appearance!s}) !== "inherit" && '
            f"reflexUITheme.background, reflexUITheme[{ThemeState.appearance!s}])"
        )
    ]


def test_plugin_wraps_every_app_in_its_theme(
    indigo_plugin: UIPlugin, compile_page: Callable[..., CompileContext]
):
    """A page asks for the wrap, inside the one of Radix Themes."""
    wraps = compile_page(lambda: rx.el.main("hello"), indigo_plugin).app_wrap_components
    assert list(wraps) == [(15, "ReflexUITheme")]
    assert type(wraps[15, "ReflexUITheme"]) is AppTheme
    assert APP_THEME_WRAP == (15, "ReflexUITheme")


def test_nested_theme_page_source(
    indigo_plugin: UIPlugin, compile_page: Callable[..., CompileContext]
):
    """A literal option imports one module, and the element stays a div."""

    def page():
        return rx.el.main(
            rx.ui.theme(
                rx.ui.box("red", style={"color": rx.ui.tokens.accent[9]}),
                accent_color="red",
            ),
            rx.ui.theme(
                "dark",
                appearance="dark",
                radius="full",
                class_name="p-8",
                style={"padding": "4px"},
                id="dark",
            ),
            rx.ui.theme("plain"),
        )

    assert compile_page(page).compiled_pages["/"].output_code == NESTED_PAGE


def test_theme_bound_to_state_imports_every_accent(
    indigo_plugin: UIPlugin, compile_page: Callable[..., CompileContext]
):
    """The element moves to a module of its own, which chooses among them."""

    def page():
        return rx.el.main(
            rx.ui.theme(
                "accent",
                accent_color=ThemeState.accent,  # pyright: ignore [reportArgumentType]
            ),
            rx.ui.theme(
                "names",
                accent_color=ThemeState.accent,  # pyright: ignore [reportArgumentType]
                gray_color="sand",
                class_name=ThemeState.names,
            ),
        )

    ctx = compile_page(page)
    assert ctx.compiled_pages["/"].output_code == BOUND_PAGE
    files, _ = compiler.compile_memo_components(ctx.auto_memo_components.values())
    sources = [code for path, code in files if "Themeelement_div_" in path]
    assert sources == [BOUND_ACCENT_THEME, BOUND_NAMES_THEME]


def test_theme_is_a_name_of_the_ui_namespace():
    assert rx.ui.theme == ThemeElement.create
    assert rx.ui.Theme is Theme
    assert {"theme", "Theme"} <= set(dir(rx.ui))


def test_theme_needs_the_plugin(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(get_config(), "plugins", [])
    with pytest.raises(ConfigError) as error:
        rx.ui.theme("hello", accent_color="red").render()
    assert str(error.value) == (
        "rx.ui components need rx.plugins.UIPlugin() in rxconfig.py plugins."
    )


def test_theme_refuses_a_value_an_option_does_not_take(indigo_plugin: UIPlugin):
    with pytest.raises(ThemeError) as error:
        rx.ui.theme("hello", accent_color="indgo").render()  # pyright: ignore [reportArgumentType]
    assert str(error.value) == (
        'rx.ui.theme: unknown accent_color "indgo". Did you mean "indigo"? The '
        'values are "tomato", "red", "ruby", "crimson", "pink", "plum", '
        '"purple", "violet", "iris", "indigo", "blue", "cyan", "teal", "jade", '
        '"green", "grass", "brown", "orange", "sky", "mint", "lime", "yellow", '
        '"amber", "gold", "bronze", "gray".'
    )


def test_theme_held_in_state_cannot_be_applied():
    """Its code never reaches the StyleX compiler, which has the class names."""
    with pytest.raises(ThemeError) as error:
        serialize(rx.ui.theme("hello", accent_color="red"))
    assert str(error.value) == (
        "rx.ui.theme: a theme rendered from state cannot be applied: its code "
        "is evaluated in the browser and never reaches the StyleX compiler. "
        "Render the theme in a page, and what comes from state inside it."
    )
