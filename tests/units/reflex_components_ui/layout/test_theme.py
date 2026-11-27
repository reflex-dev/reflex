"""Tests for reflex_components_ui.layout.theme."""

from collections.abc import Callable

import pytest
from pytest_mock import MockerFixture
from reflex_base.config import get_config
from reflex_base.plugins import CompileContext
from reflex_base.utils.exceptions import ConfigError
from reflex_base.utils.serializers import serialize
from reflex_components_core.base.app_wrap import AppWrap
from reflex_components_ui.layout.theme import AppTheme, ThemeElement
from reflex_components_ui.plugin import APP_THEME_WRAP, UIPlugin
from reflex_components_ui.themes import Theme, ThemeError

import reflex as rx
from reflex.compiler import compiler

APP_ROOT = """
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

function ReflexProviders({children}) {
  useEffect(() => {
    // Make contexts and state objects available globally for dynamic eval'd components
    window.__reflex = {
      
    };
  }, []);

  return jsx(ThemeProvider, {defaultTheme: defaultColorMode, attribute: "class"},
    jsx(AppWrap, {}, children)
  );
}


function AppWrap({children}) {

return (jsx("div",{...stylex.props(spaceScope, radiusScope, typographyScope, shadowScope, colorScope, focusScope, accentIndigo, graySlate, radiusLarge, scaling100, panelTranslucent, reflexUITheme.root, reflexUITheme.background, sx_c1c0436182.s, { $$css: true, className: "reflex-ui-theme" })},jsx(Fragment,{},children)))
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

NESTED_PAGE = """import * as stylex from "@stylexjs/stylex"
import {accentRed} from "$/reflex-ui/themes/accent/red.js"
import {focusScope} from "$/reflex-ui/themes/focus.js"
import {grayMauve} from "$/reflex-ui/themes/gray/mauve.js"
import {colorScope,radiusScope,shadowScope,spaceScope,typographyScope} from "$/reflex-ui/themes/scope.js"
import {theme as reflexUITheme} from "$/reflex-ui/themes/theme.js"
import {useRegisteredRef} from "$/utils/state"
import {radiusFull} from "$/reflex-ui/themes/radius.js"
import {Fragment,useEffect} from "react"
import {jsx} from "@emotion/react"



const sx_e0e666cdfc = stylex.create({ s: {"boxSizing": "border-box", "display": "block", "color": "var(--accent-9)"} });
const sx_ffb9e340d1 = stylex.create({ s: {"padding": "4px"} });

function Component() {
const ref_dark = useRegisteredRef("ref_dark");

  return (
    jsx(Fragment,{},jsx("main",{},jsx("div",{...stylex.props(spaceScope, radiusScope, typographyScope, shadowScope, colorScope, focusScope, accentRed, grayMauve, reflexUITheme.root, { $$css: true, className: "reflex-ui-theme" })},jsx("div",{...stylex.props(sx_e0e666cdfc.s)},"red")),jsx("div",{id:"dark",ref:ref_dark,...stylex.props(spaceScope, radiusScope, typographyScope, shadowScope, colorScope, focusScope, radiusFull, reflexUITheme.root, reflexUITheme.background, reflexUITheme.dark, sx_ffb9e340d1.s, { $$css: true, className: "reflex-ui-theme dark p-8" })},"dark"),jsx("div",{...stylex.props(spaceScope, radiusScope, typographyScope, shadowScope, colorScope, focusScope, reflexUITheme.root, { $$css: true, className: "reflex-ui-theme" })},"plain")),jsx("title",{}," | Index"),jsx("meta",{content:"",property:"og:image"},))
  )
}
Component.displayName = "Component(/)";

export default Component;
"""

BOUND_PAGE = """import {Themeelement_div_0c153819fc2a864827f9e11f201c2218} from "$/utils/components/Themeelement_div_0c153819fc2a864827f9e11f201c2218"
import {Themeelement_div_7ff1171060456d23f7870cfa8fe2dfcf} from "$/utils/components/Themeelement_div_7ff1171060456d23f7870cfa8fe2dfcf"
import {Fragment,useEffect} from "react"
import {jsx} from "@emotion/react"





function Component() {


  return (
    jsx(Fragment,{},jsx("main",{},jsx(Themeelement_div_0c153819fc2a864827f9e11f201c2218,{},"accent"),jsx(Themeelement_div_7ff1171060456d23f7870cfa8fe2dfcf,{},"names")),jsx("title",{}," | Index"),jsx("meta",{content:"",property:"og:image"},))
  )
}
Component.displayName = "Component(/)";

export default Component;
"""

BOUND_ACCENT_THEME = """
import {isTrue,mergeSlotProps} from "$/utils/state"
import {useStateContext} from "$/utils/context-registry"
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
import {grayGray} from "$/reflex-ui/themes/gray/gray.js"
import {grayMauve} from "$/reflex-ui/themes/gray/mauve.js"
import {grayOlive} from "$/reflex-ui/themes/gray/olive.js"
import {graySage} from "$/reflex-ui/themes/gray/sage.js"
import {graySand} from "$/reflex-ui/themes/gray/sand.js"
import {graySlate} from "$/reflex-ui/themes/gray/slate.js"
import {colorScope,radiusScope,shadowScope,spaceScope,typographyScope} from "$/reflex-ui/themes/scope.js"
import {theme as reflexUITheme} from "$/reflex-ui/themes/theme.js"
import * as stylex from "@stylexjs/stylex"
import {jsx} from "@emotion/react"
import {Fragment,memo,useEffect} from "react"



const reflexUIAccents = { "amber": accentAmber, "blue": accentBlue, "bronze": accentBronze, "brown": accentBrown, "crimson": accentCrimson, "cyan": accentCyan, "gold": accentGold, "grass": accentGrass, "gray": accentGray, "green": accentGreen, "indigo": accentIndigo, "iris": accentIris, "jade": accentJade, "lime": accentLime, "mint": accentMint, "orange": accentOrange, "pink": accentPink, "plum": accentPlum, "purple": accentPurple, "red": accentRed, "ruby": accentRuby, "sky": accentSky, "teal": accentTeal, "tomato": accentTomato, "violet": accentViolet, "yellow": accentYellow };
const reflexUIMatchingGrays = { "amber": graySand, "blue": graySlate, "bronze": graySand, "brown": graySand, "crimson": grayMauve, "cyan": graySlate, "gold": graySand, "grass": grayOlive, "gray": grayGray, "green": graySage, "indigo": graySlate, "iris": graySlate, "jade": graySage, "lime": grayOlive, "mint": graySage, "orange": graySand, "pink": grayMauve, "plum": grayMauve, "purple": grayMauve, "red": grayMauve, "ruby": grayMauve, "sky": graySlate, "teal": graySage, "tomato": grayMauve, "violet": grayMauve, "yellow": graySand };


export const Themeelement_div_0c153819fc2a864827f9e11f201c2218 = /*#__PURE__*/ (() => {
const Themeelement_div_0c153819fc2a864827f9e11f201c2218 = memo(({children, ...rest}) => {
    const reflex___state____state__tests___units___reflex_components_ui___layout___test_theme____theme_state = useStateContext("reflex___state____state.tests___units___reflex_components_ui___layout___test_theme____theme_state", ["accent_rx_state_"])
    return(
        jsx("div",{...mergeSlotProps(rest, ({ ...stylex.props(spaceScope, radiusScope, typographyScope, shadowScope, colorScope, focusScope, reflexUIAccents[reflex___state____state__tests___units___reflex_components_ui___layout___test_theme____theme_state.accent_rx_state_], reflexUIMatchingGrays[reflex___state____state__tests___units___reflex_components_ui___layout___test_theme____theme_state.accent_rx_state_], reflexUITheme.root, { $$css: true, className: "reflex-ui-theme" }) }))},children)
    )
});
Themeelement_div_0c153819fc2a864827f9e11f201c2218.displayName = "ThemeElement";
return Themeelement_div_0c153819fc2a864827f9e11f201c2218;
})();
"""

BOUND_NAMES_THEME = """
import {isTrue,mergeSlotProps} from "$/utils/state"
import {useStateContext} from "$/utils/context-registry"
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
import * as stylex from "@stylexjs/stylex"
import {jsx} from "@emotion/react"
import {Fragment,memo,useEffect} from "react"



const reflexUIAccents = { "amber": accentAmber, "blue": accentBlue, "bronze": accentBronze, "brown": accentBrown, "crimson": accentCrimson, "cyan": accentCyan, "gold": accentGold, "grass": accentGrass, "gray": accentGray, "green": accentGreen, "indigo": accentIndigo, "iris": accentIris, "jade": accentJade, "lime": accentLime, "mint": accentMint, "orange": accentOrange, "pink": accentPink, "plum": accentPlum, "purple": accentPurple, "red": accentRed, "ruby": accentRuby, "sky": accentSky, "teal": accentTeal, "tomato": accentTomato, "violet": accentViolet, "yellow": accentYellow };


export const Themeelement_div_7ff1171060456d23f7870cfa8fe2dfcf = /*#__PURE__*/ (() => {
const Themeelement_div_7ff1171060456d23f7870cfa8fe2dfcf = memo(({children, ...rest}) => {
    const reflex___state____state__tests___units___reflex_components_ui___layout___test_theme____theme_state = useStateContext("reflex___state____state.tests___units___reflex_components_ui___layout___test_theme____theme_state", ["names_rx_state_", "accent_rx_state_"])
    return(
        jsx("div",{...mergeSlotProps(rest, ({ className:(reflex___state____state__tests___units___reflex_components_ui___layout___test_theme____theme_state.names_rx_state_) + " " + stylex.props(spaceScope, radiusScope, typographyScope, shadowScope, colorScope, focusScope, reflexUIAccents[reflex___state____state__tests___units___reflex_components_ui___layout___test_theme____theme_state.accent_rx_state_], graySand, reflexUITheme.root, { $$css: true, className: "reflex-ui-theme" }).className }))},children)
    )
});
Themeelement_div_7ff1171060456d23f7870cfa8fe2dfcf.displayName = "ThemeElement";
return Themeelement_div_7ff1171060456d23f7870cfa8fe2dfcf;
})();
"""


class ThemeState(rx.State):
    """State whose fields are bound to a theme."""

    accent: str = "red"
    names: str = "wide"


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
            rx.ui.theme("accent", accent_color=ThemeState.accent),
            rx.ui.theme(
                "names",
                accent_color=ThemeState.accent,
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
    assert ThemeElement._display_name() == "rx.ui.theme"


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
