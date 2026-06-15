"""Tests for source-module capture and mirrored-path translation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

from reflex_base.utils import memo_paths


def _user_fn():
    """Stand-in for a user-defined function (defined in this test module)."""


def test_capture_source_module_returns_user_module():
    captured = memo_paths.capture_source_module(_user_fn)
    # Module name depends on how pytest collected this module; either is fine
    # so long as it isn't filtered.
    assert captured is not None
    assert "test_memo_paths" in captured


def test_capture_source_module_filters_framework():
    assert memo_paths.capture_source_module(memo_paths.capture_source_module) is None


def test_capture_source_module_filters_main():
    fn = type("F", (), {"__module__": "__main__"})
    assert memo_paths.capture_source_module(fn) is None


def test_capture_source_module_filters_missing():
    assert memo_paths.capture_source_module(None) is None
    fn = type("F", (), {"__module__": ""})
    assert memo_paths.capture_source_module(fn) is None


def test_module_to_mirrored_segments_module():
    spec = importlib.util.find_spec("reflex.app")
    # Ensure the test runs against a real, non-package module.
    assert spec is not None
    assert spec.origin
    assert not spec.origin.endswith("__init__.py")
    segments = memo_paths.module_to_mirrored_segments("reflex.app")
    assert segments == ("reflex", "app")


def test_module_to_mirrored_segments_package_appends_index():
    # `reflex.components` is a package — its __init__.py origin should
    # cause an "index" segment to be appended.
    segments = memo_paths.module_to_mirrored_segments("reflex.components")
    assert segments == ("reflex", "components", "index")


def test_module_to_mirrored_segments_unsafe_segment_rejected():
    assert memo_paths.module_to_mirrored_segments("foo..bar") is None
    assert memo_paths.module_to_mirrored_segments("foo./bar") is None
    assert memo_paths.module_to_mirrored_segments("..secret") is None


def test_module_to_mirrored_segments_rejects_windows_reserved_names():
    # Reserved device names (any case) can't be created as files on Windows, so
    # a module with such a segment falls back to the un-mirrored path.
    assert memo_paths.module_to_mirrored_segments("myapp.con") is None
    assert memo_paths.module_to_mirrored_segments("aux") is None
    assert memo_paths.module_to_mirrored_segments("myapp.COM1") is None
    assert memo_paths.module_to_mirrored_segments("myapp.lpt9.ui") is None
    # A name merely containing a reserved name is fine.
    assert memo_paths.module_to_mirrored_segments("myapp.controls") == (
        "myapp",
        "controls",
    )


def test_segment_is_safe_rejects_trailing_dot_or_space():
    assert memo_paths._segment_is_safe("ok")
    assert not memo_paths._segment_is_safe("trailing.")
    assert not memo_paths._segment_is_safe("trailing ")


def test_is_framework_module_covers_packages_and_prefixes():
    def _fn_in(module: str):
        return type("F", (), {"__module__": module})

    # The package itself and its submodules are framework.
    assert memo_paths.capture_source_module(_fn_in("reflex")) is None
    assert memo_paths.capture_source_module(_fn_in("reflex.app")) is None
    assert memo_paths.capture_source_module(_fn_in("reflex_base")) is None
    # The reflex_components_* family matches by prefix.
    assert memo_paths.capture_source_module(_fn_in("reflex_components_radix")) is None
    # A user module that merely starts with "reflex" but isn't a framework
    # package is still mirrored.
    assert (
        memo_paths.capture_source_module(_fn_in("reflexion.pages")) == "reflexion.pages"
    )


def test_library_for_mirrors_or_falls_back():
    assert (
        memo_paths.library_for("counter_app.ui", "Button")
        == "$/app_components/counter_app/ui"
    )
    # No source module → per-name internal path.
    assert memo_paths.library_for(None, "Button") == "$/app_components/_internal/Button"
    # Unsafe module → per-name internal path.
    assert (
        memo_paths.library_for("bad..name", "Button")
        == "$/app_components/_internal/Button"
    )


def test_module_to_mirrored_segments_none():
    assert memo_paths.module_to_mirrored_segments(None) is None
    assert memo_paths.module_to_mirrored_segments("") is None


def test_mirrored_jsx_path_joins_segments():
    web_dir = Path("/tmp/.web")
    path = memo_paths.mirrored_jsx_path(web_dir, ("counter_app", "ui", "buttons"))
    assert path == web_dir / "app_components" / "counter_app" / "ui" / "buttons.jsx"


def test_mirrored_library_specifier_joins_with_slash():
    spec = memo_paths.mirrored_library_specifier(("counter_app", "ui", "buttons"))
    assert spec == "$/app_components/counter_app/ui/buttons"


def test_mirrored_paths_live_under_reserved_app_components_dir():
    """User module paths are nested under app_components/, so they can't clobber framework output."""
    assert memo_paths.mirrored_jsx_path(Path(".web"), ("app", "root")) == Path(
        ".web/app_components/app/root.jsx"
    )
    assert (
        memo_paths.mirrored_library_specifier(("app", "root"))
        == "$/app_components/app/root"
    )


def test_resolve_user_module_from_frame_skips_framework():
    captured = memo_paths.resolve_user_module_from_frame()
    # Must find a user frame — the test module itself qualifies.
    assert captured is not None
    assert not captured.startswith("reflex")


def test_resolve_user_module_from_frame_returns_none_inside_framework_only():
    # Simulate a stack of framework-only frames.
    with patch.object(memo_paths, "_is_framework_module", return_value=True):
        assert memo_paths.resolve_user_module_from_frame() is None
