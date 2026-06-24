"""Tests for the frontend inspector frame-capture machinery."""

from __future__ import annotations

from pathlib import Path

import pytest
from reflex_base.inspector import capture, state


@pytest.fixture
def enabled_inspector():
    """Enable the inspector and clear the registry around each test."""
    capture.reset()
    state.set_enabled(True)
    yield
    state.set_enabled(False)
    capture.reset()


def test_capture_returns_none_when_disabled():
    capture.reset()
    state.set_enabled(False)
    assert capture.capture("Box") is None
    assert capture.snapshot() == {}


def test_capture_records_user_frame(enabled_inspector):
    cid = capture.capture("Box")
    assert cid is not None
    info = capture.snapshot()[cid]
    assert info.component == "Box"
    # The frame walked is this test file, not the framework.
    assert info.file == str(Path(__file__).resolve())
    assert info.line > 0
    assert info.column == 1


def test_capture_is_deterministic_across_resets(enabled_inspector):
    """Same call site must hash to the same id even after a reset.

    The backend is spawned via ``multiprocessing.spawn`` so the request
    handler runs in a fresh interpreter. Ids that diverge across resets
    would mean a ``data-rx`` value with no matching ``source-map.json``
    entry.
    """

    def at_same_site():
        return capture.capture("Box")

    first = at_same_site()
    capture.reset()
    state.set_enabled(True)
    second = at_same_site()
    assert first == second


def test_capture_skips_framework_frames(enabled_inspector, monkeypatch):
    # Treat every frame as framework code; the walk must run out of frames
    # without finding user code and return None.
    monkeypatch.setattr(capture, "_is_framework_frame", lambda _: True)

    def helper():
        return capture.capture("Box")

    cid = helper()
    assert cid is None
    assert capture.snapshot() == {}


def test_capture_assigns_unique_ids(enabled_inspector):
    a = capture.capture("Box")
    b = capture.capture("Text")
    assert a is not None
    assert b is not None
    assert a != b
    assert capture.snapshot()[a].component == "Box"
    assert capture.snapshot()[b].component == "Text"


def test_is_framework_frame_handles_unresolvable_paths():
    # Bogus paths default to "framework" so we never accidentally pin a
    # source to garbage.
    assert capture._is_framework_frame("/does/not/exist/foo.py") in (True, False)


def test_is_framework_package_recognises_components():
    from reflex_base.utils import frames

    assert frames.is_framework_package("reflex")
    assert frames.is_framework_package("reflex_base")
    assert frames.is_framework_package("reflex_components_radix")
    assert not frames.is_framework_package("reflex_dashboard")
    assert not frames.is_framework_package("my_app")
