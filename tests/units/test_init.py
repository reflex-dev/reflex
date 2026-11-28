"""Tests for the top-level reflex namespace."""

import importlib
import subprocess
import sys

import pytest
import reflex_components_ui

import reflex as rx

UI_NOT_INSTALLED = (
    "`rx.ui` requires the reflex-components-ui package, which is not installed. "
    "Install it with `pip install 'reflex[ui]'`."
)


@pytest.fixture
def unresolved_ui(monkeypatch: pytest.MonkeyPatch):
    """Forget that `rx.ui` was resolved, so the next access imports it again.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.delitem(vars(rx), "ui", raising=False)


def test_ui_resolves_to_the_components_package(unresolved_ui: None):
    assert rx.ui is reflex_components_ui
    # Cached on the module, so later accesses skip __getattr__.
    assert vars(rx)["ui"] is reflex_components_ui


def test_ui_is_listed():
    assert rx.__all__.count("ui") == 1
    assert dir(rx) == sorted(rx.__all__)


def test_importing_reflex_does_not_import_ui():
    """`rx.ui` costs nothing until it is used."""
    code = (
        "import sys, reflex\n"
        "print('reflex_components_ui' in sys.modules)\n"
        "reflex.ui\n"
        "print('reflex_components_ui' in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout == "False\nTrue\n"


def test_ui_without_the_extra_says_what_to_install(
    unresolved_ui: None, monkeypatch: pytest.MonkeyPatch
):
    # A None entry makes the import system report the module as not found.
    monkeypatch.setitem(sys.modules, "reflex_components_ui", None)
    with pytest.raises(ModuleNotFoundError) as raised:
        rx.ui
    assert str(raised.value) == UI_NOT_INSTALLED
    assert raised.value.name == "reflex_components_ui"
    assert "ui" not in vars(rx)


def test_ui_does_not_hide_a_missing_dependency_of_the_package(
    unresolved_ui: None, monkeypatch: pytest.MonkeyPatch
):
    """Only the package itself being absent means the extra is not installed."""
    error = ModuleNotFoundError("No module named 'other'", name="other")

    def import_module(name: str):
        raise error

    monkeypatch.setattr(importlib, "import_module", import_module)
    with pytest.raises(ModuleNotFoundError) as raised:
        rx.ui
    assert raised.value is error
