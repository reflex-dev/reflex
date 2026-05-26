"""Tests for the global enabled flag."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from reflex_base import constants
from reflex_base.inspector import PUBLIC_DIRNAME, SOURCE_MAP_FILENAME, state


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """Isolate module globals + env var so tests can't leak into each other."""
    monkeypatch.delenv(state._ENV_KEY, raising=False)
    monkeypatch.setattr(state, "_ENABLED", None)
    yield
    monkeypatch.setattr(state, "_ENABLED", None)


def test_default_disabled():
    state.set_enabled(False)
    assert state.is_enabled() is False


def test_set_enabled_round_trip():
    state.set_enabled(True)
    assert state.is_enabled() is True
    state.set_enabled(False)
    assert state.is_enabled() is False


def test_disable_clears_env_var():
    """Disabling must not leave a sentinel value in os.environ.

    Writing ``"0"`` on disable would pollute every subprocess spawned
    afterwards, since ``os.environ`` is inherited on ``fork``/``spawn``.
    """
    state.set_enabled(True)
    assert os.environ.get(state._ENV_KEY) == "1"
    state.set_enabled(False)
    assert state._ENV_KEY not in os.environ


def test_is_enabled_honors_env_var(monkeypatch):
    """A worker process inherits the env var from its parent."""
    monkeypatch.setenv(state._ENV_KEY, "1")
    assert state.is_enabled() is True


def test_is_enabled_env_var_zero_disables(monkeypatch):
    monkeypatch.setenv(state._ENV_KEY, "0")
    assert state.is_enabled() is False


def _write_source_map(web_dir: Path) -> Path:
    artifact = web_dir / constants.Dirs.PUBLIC / PUBLIC_DIRNAME / SOURCE_MAP_FILENAME
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("{}")
    return artifact


def test_is_enabled_falls_back_to_source_map(monkeypatch, tmp_path):
    """No env var, no set_enabled — source-map.json on disk wins.

    This is the worker-process path: ``reflex run`` performs compile in a
    one-shot subprocess that exits before the Granian worker is spawned,
    so the worker never observes the in-memory ``set_enabled(True)`` nor
    inherits the env var written inside the compile child. It has to
    discover the build's intent from the on-disk artifact.
    """
    monkeypatch.setenv("REFLEX_WEB_WORKDIR", str(tmp_path))
    _write_source_map(tmp_path)
    assert state.is_enabled() is True


def test_is_enabled_falls_back_to_disabled_when_no_source_map(monkeypatch, tmp_path):
    monkeypatch.setenv("REFLEX_WEB_WORKDIR", str(tmp_path))
    assert state.is_enabled() is False


def test_env_var_overrides_source_map(monkeypatch, tmp_path):
    """Explicit env var beats the on-disk artifact (kill-switch for tests)."""
    monkeypatch.setenv("REFLEX_WEB_WORKDIR", str(tmp_path))
    _write_source_map(tmp_path)
    monkeypatch.setenv(state._ENV_KEY, "0")
    assert state.is_enabled() is False
