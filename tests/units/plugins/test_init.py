"""Tests for the names reflex.plugins resolves on first use."""

import subprocess
import sys

import pytest
import reflex_components_ui.plugin

import reflex as rx
import reflex.plugins


@pytest.fixture
def unresolved_ui_plugin(monkeypatch: pytest.MonkeyPatch):
    """Forget that `UIPlugin` was resolved, so the next access imports it again.

    Args:
        monkeypatch: The pytest fixture that restores the module afterwards.
    """
    monkeypatch.delitem(vars(reflex.plugins), "UIPlugin", raising=False)


def test_ui_plugin_resolves_to_the_plugin_of_the_components_package(
    unresolved_ui_plugin: None,
):
    assert rx.plugins.UIPlugin is reflex_components_ui.plugin.UIPlugin
    # Resolved once: the module attribute now answers.
    assert vars(reflex.plugins)["UIPlugin"] is reflex_components_ui.plugin.UIPlugin


def test_importing_reflex_plugins_does_not_import_the_components_package():
    code = (
        "import sys, reflex.plugins\n"
        "from reflex.plugins import *\n"
        "print('reflex_components_ui' in sys.modules)\n"
        "reflex.plugins.UIPlugin\n"
        "print('reflex_components_ui' in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout == "False\nTrue\n"


class _NotInstalled:
    """A finder that answers as the import system does for an absent package."""

    @staticmethod
    def find_spec(name: str, path: object = None, target: object = None) -> None:
        """Refuse to find the components package.

        Args:
            name: The module being imported.
            path: The search path of its parent package.
            target: The module being reloaded.

        Raises:
            ModuleNotFoundError: If the module belongs to the package.
        """
        if name.partition(".")[0] == "reflex_components_ui":
            msg = f"No module named {name!r}"
            raise ModuleNotFoundError(msg, name="reflex_components_ui")


def test_ui_plugin_without_the_extra_says_what_to_install(
    unresolved_ui_plugin: None, monkeypatch: pytest.MonkeyPatch
):
    for name in [
        name for name in sys.modules if name.startswith("reflex_components_ui")
    ]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(sys, "meta_path", [_NotInstalled, *sys.meta_path])
    with pytest.raises(ModuleNotFoundError) as raised:
        rx.plugins.UIPlugin
    assert str(raised.value) == (
        "`rx.plugins.UIPlugin` requires the reflex-components-ui package, which is "
        "not installed. Install it with `pip install 'reflex[ui]'`."
    )
    assert raised.value.name == "reflex_components_ui"
    assert "UIPlugin" not in vars(reflex.plugins)


def test_ui_plugin_does_not_hide_a_missing_dependency_of_the_package(
    unresolved_ui_plugin: None, monkeypatch: pytest.MonkeyPatch
):
    """Only the package itself being absent means the extra is not installed."""
    monkeypatch.delitem(sys.modules, "reflex_components_ui.plugin")
    monkeypatch.setitem(sys.modules, "reflex_components_ui.constants", None)
    with pytest.raises(ModuleNotFoundError) as raised:
        rx.plugins.UIPlugin
    assert raised.value.name == "reflex_components_ui.constants"


def test_unknown_plugin_is_an_attribute_error():
    with pytest.raises(AttributeError) as raised:
        rx.plugins.NoSuchPlugin  # pyright: ignore[reportAttributeAccessIssue]
    assert str(raised.value) == (
        "module 'reflex.plugins' has no attribute 'NoSuchPlugin'"
    )
