"""Tests for the gradient profile component."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import reflex.assets

MODULE = "reflex_components_internal.components.base.gradient_profile"


def _javascript_source() -> str:
    """Read the bundled GradientProfile JavaScript source.

    Returns:
        The JavaScript source text.
    """
    module = importlib.import_module(MODULE)
    assert module.__file__ is not None
    return Path(module.__file__).with_name("GradientProfile.js").read_text()


def test_import_does_not_resolve_asset(monkeypatch) -> None:
    """Importing the component must not create a shared-asset symlink."""
    calls = []

    def tracking_asset(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(importable_path="$/public/stub.js")

    monkeypatch.setattr(reflex.assets, "asset", tracking_asset)

    original = sys.modules.pop(MODULE, None)
    try:
        importlib.import_module(MODULE)
        assert calls == []
    finally:
        if original is not None:
            sys.modules[MODULE] = original
        else:
            sys.modules.pop(MODULE, None)


def test_create_resolves_shared_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Creating the component links its JavaScript asset into the app."""
    from reflex_components_internal.components.base.gradient_profile import (
        GradientProfile,
    )

    monkeypatch.chdir(tmp_path)
    component = GradientProfile.create()

    assert component.library is not None
    assert component.library.endswith(
        "/reflex_components_internal/components/base/gradient_profile/GradientProfile.js"
    )
    assert (
        tmp_path
        / "assets/external/reflex_components_internal/components/base/gradient_profile/GradientProfile.js"
    ).is_symlink()


def test_create_with_library_override_does_not_resolve_asset(monkeypatch) -> None:
    """A caller-supplied library must bypass shared-asset resolution."""
    module = importlib.import_module(MODULE)
    calls = []

    def tracking_asset(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(importable_path="$/public/stub.js")

    monkeypatch.setattr(module, "asset", tracking_asset)
    component = module.GradientProfile.create(library="custom-library")

    assert calls == []
    assert component.library == "custom-library"


def test_javascript_merges_caller_style_with_gradient() -> None:
    """Caller styles must not replace the generated gradient style."""
    source = _javascript_source()

    assert "  style," in source
    assert "style: { ...style, ...gradientStyle }," in source


def test_javascript_is_decorative_by_default() -> None:
    """The gradient div must not default to an unnamed image role."""
    assert 'role: "img"' not in _javascript_source()
