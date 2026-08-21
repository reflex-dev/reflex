import pytest
from reflex_components_core.ui.plugin import (
    THEME_STYLESHEET_IMPORT,
    THEME_STYLESHEET_PATH,
    UIComponentsPlugin,
)
from reflex_components_core.ui.theme import Theme


@pytest.fixture
def no_ui_components_created(mocker):
    """Pretend no UI component has been created in this process.

    Args:
        mocker: The pytest-mock fixture.

    Returns:
        The pytest-mock fixture, for further patching.
    """
    mocker.patch(
        "reflex_components_core.ui.base._ui_component_created",
        False,
    )
    return mocker


def test_explicit_plugin_serves_theme_stylesheet(no_ui_components_created) -> None:
    """An explicitly configured plugin always emits the theme stylesheet."""
    plugin = UIComponentsPlugin(theme=Theme(radius="2rem"))

    assert plugin.get_stylesheet_paths() == (THEME_STYLESHEET_IMPORT,)
    ((path, content),) = plugin.get_static_assets()
    assert path == THEME_STYLESHEET_PATH
    assert "--radius: 2rem;" in content
    assert "--background" in content


def test_implicit_plugin_starts_disabled(no_ui_components_created) -> None:
    """The compile-local plugin contributes nothing until enabled."""
    plugin = UIComponentsPlugin.create_implicit()

    assert plugin.get_stylesheet_paths() == ()
    assert plugin.get_static_assets() == ()


def test_implicit_plugin_enables_when_ui_component_created(mocker) -> None:
    """Creating any UI component enables the implicit plugin's assets.

    This covers UI components that never pass through the page compiler
    hooks, such as components inside rx.memo.
    """
    mocker.patch(
        "reflex_components_core.ui.base._ui_component_created",
        True,
    )
    plugin = UIComponentsPlugin.create_implicit()

    assert plugin.get_stylesheet_paths() == (THEME_STYLESHEET_IMPORT,)
    assert plugin.get_static_assets() != ()


def test_explicitly_disabled_plugin_stays_disabled(mocker) -> None:
    """A user-disabled plugin never ships assets, even with UI components."""
    mocker.patch(
        "reflex_components_core.ui.base._ui_component_created",
        True,
    )
    plugin = UIComponentsPlugin(enabled=False)

    assert plugin.get_stylesheet_paths() == ()
    assert plugin.get_static_assets() == ()


def test_creating_a_ui_component_sets_the_flag(no_ui_components_created) -> None:
    """UIComponent creation flips the created flag read by the plugin."""
    from reflex_components_core.ui import base

    import reflex as rx

    rx.ui.badge("hi")

    assert base._ui_component_created


def test_enter_component_enables_on_ui_component(
    no_ui_components_created,
) -> None:
    """Compiling a UI component auto-enables the implicit plugin."""
    import reflex as rx

    mocker = no_ui_components_created
    mocker.patch(
        "reflex_components_core.ui.plugin._tailwind_v4_plugin_active",
        return_value=True,
    )
    plugin = UIComponentsPlugin.create_implicit()

    plugin.enter_component(
        rx.el.div(), page_context=mocker.Mock(), compile_context=None
    )
    assert not plugin.enabled

    button = rx.ui.button("hi")
    mocker.patch(
        "reflex_components_core.ui.base._ui_component_created",
        False,
    )
    plugin.enter_component(button, page_context=mocker.Mock(), compile_context=None)
    assert plugin.enabled
    assert plugin.get_stylesheet_paths() == (THEME_STYLESHEET_IMPORT,)


def test_enter_component_warns_without_tailwind(mocker) -> None:
    """Enabling without the Tailwind v4 plugin warns once."""
    import reflex as rx

    mocker.patch(
        "reflex_components_core.ui.plugin._tailwind_v4_plugin_active",
        return_value=False,
    )
    warn = mocker.patch("reflex_components_core.ui.plugin.console.warn")
    plugin = UIComponentsPlugin.create_implicit()

    plugin.enter_component(
        rx.ui.button("hi"), page_context=mocker.Mock(), compile_context=None
    )
    plugin.enter_component(
        rx.ui.button("again"), page_context=mocker.Mock(), compile_context=None
    )

    warn.assert_called_once()
    assert "TailwindV4Plugin" in warn.call_args.args[0]
