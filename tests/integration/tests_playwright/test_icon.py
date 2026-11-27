"""Integration tests for the Icon component.

The app also carries a plugin that adds a Vite plugin, since it already builds
in both dev and prod.
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect
from reflex_components_lucide.icon import LUCIDE_ICON_LIST

from reflex.testing import AppHarness

VITE_CONSTANT = "defined by a vite plugin"


def Icons(vite_constant: str = VITE_CONSTANT):
    """App rendering every icon, built with a plugin-contributed Vite plugin.

    Args:
        vite_constant: The value the Vite plugin defines for the page to read.
    """
    import json
    from pathlib import Path

    from reflex_components_lucide.icon import LUCIDE_ICON_LIST

    import reflex as rx

    class DefineConstantPlugin(rx.plugins.Plugin):
        """Adds a Vite plugin, shipped in the app, that defines a constant."""

        def get_static_assets(self, **context):
            """Write the Vite plugin's module into ``.web``.

            Args:
                context: The context for the plugin.

            Returns:
                The module's path and source.
            """
            return [
                (
                    Path("vite-plugin-define-constants.js"),
                    (
                        "export default function defineConstants(constants) {\n"
                        '  return { name: "define-constants", config: () => ({ define: constants }) };\n'
                        "}\n"
                    ),
                )
            ]

        def get_vite_plugins(self, **context):
            """Add the Vite plugin to ``vite.config.js``.

            Args:
                context: The context for the plugin.

            Returns:
                The entry importing and calling the module.
            """
            # Doubly encoded: once as a JS string literal in the config, and
            # once more because `define` substitutes source text.
            value = json.dumps(json.dumps(vite_constant))
            return [
                rx.plugins.VitePluginEntry(
                    imports=[
                        'import defineConstants from "./vite-plugin-define-constants.js"'
                    ],
                    call=f"defineConstants({{ __REFLEX_TEST_VITE_CONSTANT__: {value} }})",
                )
            ]

    app = rx.App()
    # Set plugins after rx.App(), which reloads the config from rxconfig.py.
    config = rx.config.get_config()
    config.plugins = [*config.plugins, DefineConstantPlugin()]

    class State(rx.State):
        """State for the Icons app."""

        dynamic_icon: str = "airplay"

    @app.add_page
    def index():
        return rx.vstack(
            rx.el.input(
                custom_attrs={"id": "token"},
                value=State.router.session.client_token,
                is_read_only=True,
            ),
            rx.el.div(
                rx.icon(State.dynamic_icon),
                id="dynamic_icon",
            ),
            rx.el.div(
                rx.Var("__REFLEX_TEST_VITE_CONSTANT__", _var_type=str),
                id="vite_constant",
            ),
            *[
                rx.el.div(rx.icon(icon_name), id=icon_name)
                for icon_name in LUCIDE_ICON_LIST
            ],
        )


@pytest.fixture(scope="module")
def icons(
    tmp_path_factory, app_harness_env: type[AppHarness]
) -> Generator[AppHarness, None, None]:
    """Start the icon app with the selected harness mode.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture.
        app_harness_env: harness class for the dev or prod mode under test.

    Yields:
        The running app harness.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("icons"),
        app_source=Icons,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_icons(icons: AppHarness, page: Page) -> None:
    """All static and state-driven icons render as SVGs.

    Args:
        icons: harness for the icon app.
        page: Playwright page.
    """
    assert icons.frontend_url is not None
    page.goto(icons.frontend_url)
    expect(page.locator("#token")).not_to_have_value("", timeout=30_000)

    for icon_name in [*LUCIDE_ICON_LIST, "dynamic_icon"]:
        expect(page.locator(f'[id="{icon_name}"] svg')).to_have_count(1)


def test_vite_plugin_from_reflex_plugin(icons: AppHarness, page: Page) -> None:
    """A constant defined by a plugin-contributed Vite plugin reaches the page.

    Args:
        icons: harness for the icon app.
        page: Playwright page.
    """
    assert icons.frontend_url is not None
    page.goto(icons.frontend_url)

    expect(page.locator("#vite_constant")).to_have_text(VITE_CONSTANT)
