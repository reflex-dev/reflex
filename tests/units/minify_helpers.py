"""Helpers for installing a ``minify.json`` in unit tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from reflex_base.registry import RegistrationContext

from reflex.environment import environment
from reflex.minify import (
    MINIFY_JSON,
    SCHEMA_VERSION,
    MinifyConfig,
    StateEntry,
    clear_config_cache,
    save_minify_config,
)
from reflex.state import BaseState


def resolved_event_id(state_cls: type[BaseState], handler_name: str) -> str | None:
    """Resolve a handler's minified id through the active resolver.

    Args:
        state_cls: The state owning the handler.
        handler_name: The handler's Python name.

    Returns:
        The minified id, or ``None`` when the handler is not minified.
    """
    return RegistrationContext.get().name_resolver.resolve_handler_name(
        state_cls, handler_name
    )


def set_minify_modes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    states: bool | None = None,
    events: bool | None = None,
) -> None:
    """Set ``REFLEX_MINIFY_*`` env vars; ``None`` leaves the var unchanged.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        states: Whether ``REFLEX_MINIFY_STATES`` is on.
        events: Whether ``REFLEX_MINIFY_EVENTS`` is on.
    """
    if states is not None:
        monkeypatch.setenv(environment.REFLEX_MINIFY_STATES.name, str(int(states)))
    if events is not None:
        monkeypatch.setenv(environment.REFLEX_MINIFY_EVENTS.name, str(int(events)))


def install_config(
    states: dict[str, str | StateEntry] | None = None,
    events: dict[str, dict[str, str]] | None = None,
    *,
    include_state_root: bool = False,
) -> MinifyConfig:
    """Build, save, and activate a ``minify.json`` in one call.

    Calls ``clear_config_cache()`` afterward — that re-installs the resolver
    and clears every per-class lru_cache, so tests don't need to call
    ``State.get_name.cache_clear()`` etc. by hand.

    Args:
        states: ``state_path -> minified_id`` map. Plain string values are
            wrapped into :class:`StateEntry` with ``parent=None``.
        events: ``state_path -> {handler -> minified_id}`` map.
        include_state_root: Add ``"reflex.state.State": "a"`` so subclasses
            of ``State`` resolve through the root entry.

    Returns:
        The saved config.
    """
    states_map: dict[str, StateEntry] = {
        path: value if isinstance(value, dict) else StateEntry(id=value, parent=None)
        for path, value in (states or {}).items()
    }
    if include_state_root:
        states_map.setdefault("reflex.state.State", StateEntry(id="a", parent=None))
    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": states_map,
        "events": events or {},
    }
    save_minify_config(config)
    clear_config_cache()
    return config


def run_in_fresh_interpreter(
    tmp_path: Path, config: MinifyConfig, script: str, **env: str
) -> None:
    """Run ``script`` in a new interpreter rooted at a directory holding ``config``.

    The framework states bake their names when ``reflex.state`` is first
    imported, so anything that depends on their minified names needs an
    interpreter that starts up with ``minify.json`` already in place.

    Args:
        tmp_path: Directory to use as the app root.
        config: The ``minify.json`` contents to write there.
        script: Python source to execute; a non-zero exit fails the test.
        env: Extra environment variables for the child process.
    """
    (tmp_path / MINIFY_JSON).write_text(json.dumps(config))
    (tmp_path / "check.py").write_text(textwrap.dedent(script))

    result = subprocess.run(
        [sys.executable, "-c", "import check"],
        cwd=tmp_path,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
