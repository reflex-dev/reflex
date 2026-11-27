"""Tests for reflex_components_ui.plugin."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from reflex_base.plugins import VitePluginEntry
from reflex_components_ui.constants import JS_SRC
from reflex_components_ui.plugin import UIPlugin, add_base_stylesheet
from reflex_components_ui.themes import Theme


def test_plugin_installs_the_style_compiler_for_the_build_only():
    plugin = UIPlugin()
    assert plugin.get_frontend_development_dependencies() == [
        "@stylexjs/stylex@0.19.2",
        "@stylexjs/unplugin@0.19.2",
        "lightningcss@1.33.0",
    ]
    assert plugin.get_frontend_dependencies() == []


def test_plugin_adds_the_wrapped_stylex_plugin_to_vite():
    assert UIPlugin().get_vite_plugins() == [
        VitePluginEntry(
            imports=(
                'import reflexUIStylex from "./reflex-ui/vite-plugin-stylex.js"',
                'import { Features as lightningcssFeatures } from "lightningcss"',
            ),
            call="""reflexUIStylex("__reflex_global_styles", {
      useCSSLayers: { prefix: "reflex-ui" },
      styleResolution: "application-order",
      lightningcssOptions: { minify: true, exclude: lightningcssFeatures.LightDark },
    })""",
        )
    ]


def test_plugin_writes_every_file_of_the_javascript_package():
    """The assets are the files under js/src, each where the app imports it."""
    shipped = {
        path.relative_to(JS_SRC).as_posix(): path.read_text()
        for path in JS_SRC.rglob("*")
        if path.is_file()
    }
    # The files this plugin itself relies on; others come with the components.
    assert {"README.md", "base.css", "vite-plugin-stylex.js"} <= shipped.keys()
    assets = UIPlugin().get_static_assets()
    assert [path for path, _ in assets] == [
        Path("reflex-ui") / name for name in sorted(shipped)
    ]
    assert {
        path.relative_to("reflex-ui").as_posix(): content for path, content in assets
    } == shipped


def test_plugin_imports_the_base_stylesheet_before_compile():
    modified = {}

    def add_save_task(task: Callable[..., Any], /, *args: Any, **kwargs: Any) -> None:
        pytest.fail("the plugin writes no file of its own before a compile")

    UIPlugin().pre_compile(
        add_save_task=add_save_task,
        add_modify_task=modified.__setitem__,
        radix_themes_plugin=None,
        unevaluated_pages=[],
    )
    assert modified == {"styles/__reflex_global_styles.css": add_base_stylesheet}


def test_base_stylesheet_is_imported_ahead_of_every_other_stylesheet():
    """Tailwind adds its import after the reset, so base.css goes before it."""
    root = (
        "@layer __reflex_base;\n"
        "@import url('./__reflex_style_reset.css');\n"
        "@import url('./tailwind.css');"
    )
    with_base = (
        "@layer __reflex_base;\n"
        "@import url('../reflex-ui/base.css');\n"
        "@import url('./__reflex_style_reset.css');\n"
        "@import url('./tailwind.css');"
    )
    assert add_base_stylesheet(root) == with_base
    assert add_base_stylesheet(with_base) == with_base
    assert add_base_stylesheet("") == "@import url('../reflex-ui/base.css');"


def test_plugin_has_a_theme():
    assert UIPlugin().theme == Theme()
    assert repr(UIPlugin()) == (
        "UIPlugin(theme=Theme(accent_color='blue', gray_color='auto', "
        "radius='medium', scaling='100%', appearance='inherit', "
        "panel_background='translucent', has_background=True))"
    )
