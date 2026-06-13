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


def test_module_to_mirrored_segments_none():
    assert memo_paths.module_to_mirrored_segments(None) is None
    assert memo_paths.module_to_mirrored_segments("") is None


def test_mirrored_jsx_path_joins_segments():
    web_dir = Path("/tmp/.web")
    path = memo_paths.mirrored_jsx_path(web_dir, ("counter_app", "ui", "buttons"))
    assert path == web_dir / "counter_app" / "ui" / "buttons.jsx"


def test_mirrored_library_specifier_joins_with_slash():
    spec = memo_paths.mirrored_library_specifier(("counter_app", "ui", "buttons"))
    assert spec == "$/counter_app/ui/buttons"


def test_resolve_user_module_from_frame_skips_framework():
    captured = memo_paths.resolve_user_module_from_frame()
    # Must find a user frame — the test module itself qualifies.
    assert captured is not None
    assert not captured.startswith("reflex")


def test_resolve_user_module_from_frame_returns_none_inside_framework_only():
    # Simulate a stack of framework-only frames.
    with patch.object(memo_paths, "_is_framework_module", return_value=True):
        assert memo_paths.resolve_user_module_from_frame() is None
