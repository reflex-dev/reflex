"""Helpers for installing a ``minify.json`` in unit tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from reflex_base.registry import RegistrationContext

from reflex.environment import environment
from reflex.minify import (
    MINIFY_JSON,
    SCHEMA_VERSION,
    MinifyConfig,
    MinifyNameResolver,
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
    vars: bool | None = None,
) -> None:
    """Set ``REFLEX_MINIFY_*`` env vars; ``None`` leaves the var unchanged.

    The resolver reads the modes when installed, so they only take effect
    through a following ``install_config()`` or ``clear_config_cache()``.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        states: Whether ``REFLEX_MINIFY_STATES`` is on.
        events: Whether ``REFLEX_MINIFY_EVENTS`` is on.
        vars: Whether ``REFLEX_MINIFY_VARS`` is on.
    """
    for env_var, enabled in (
        (environment.REFLEX_MINIFY_STATES, states),
        (environment.REFLEX_MINIFY_EVENTS, events),
        (environment.REFLEX_MINIFY_VARS, vars),
    ):
        if enabled is not None:
            monkeypatch.setenv(env_var.name, str(int(enabled)))


def make_config(
    states: Mapping[str, str | StateEntry] | None = None,
    events: dict[str, dict[str, str]] | None = None,
    vars: dict[str, dict[str, str]] | None = None,
    *,
    include_state_root: bool = False,
) -> MinifyConfig:
    """Build a ``minify.json`` config.

    Args:
        states: ``state_path -> minified_id`` map. Plain string values are
            wrapped into :class:`StateEntry` with ``parent=None``.
        events: ``state_path -> {handler -> minified_id}`` map.
        vars: ``state_path -> {var -> minified_id}`` map.
        include_state_root: Add ``"reflex.state.State": "a"`` so subclasses
            of ``State`` resolve through the root entry.

    Returns:
        The config.
    """
    states_map: dict[str, StateEntry] = {
        path: value if isinstance(value, dict) else StateEntry(id=value, parent=None)
        for path, value in (states or {}).items()
    }
    if include_state_root:
        states_map.setdefault("reflex.state.State", StateEntry(id="a", parent=None))
    return MinifyConfig(
        version=SCHEMA_VERSION,
        states=states_map,
        events=events or {},
        vars=vars or {},
    )


def write_config(directory: Path, config: Mapping[str, Any]) -> None:
    """Write ``config`` as the ``minify.json`` of ``directory``, as it is.

    Args:
        directory: The directory to write it to, created if missing.
        config: The contents, which may be malformed on purpose.
    """
    directory.mkdir(parents=True, exist_ok=True)
    (directory / MINIFY_JSON).write_text(json.dumps(config))


def install_config(
    states: Mapping[str, str | StateEntry] | None = None,
    events: dict[str, dict[str, str]] | None = None,
    vars: dict[str, dict[str, str]] | None = None,
    *,
    include_state_root: bool = False,
) -> MinifyConfig:
    """Build, save, and activate a ``minify.json`` in one call.

    Calls ``clear_config_cache()`` afterward — that re-installs the resolver
    and clears every per-class lru_cache, so tests don't need to call
    ``State.get_name.cache_clear()`` etc. by hand.

    Args:
        states: See :func:`make_config`.
        events: See :func:`make_config`.
        vars: See :func:`make_config`.
        include_state_root: See :func:`make_config`.

    Returns:
        The saved config.
    """
    config = make_config(states, events, vars, include_state_root=include_state_root)
    save_minify_config(config)
    clear_config_cache()
    return config


def minify_resolver(
    config: MinifyConfig | None = None,
    *,
    states: bool = False,
    events: bool = False,
    vars: bool = False,
) -> MinifyNameResolver:
    """Build a resolver over ``config`` with the given modes on.

    Args:
        config: The config, if any.
        states: Whether state names are minified.
        events: Whether event names are minified.
        vars: Whether var names are minified.

    Returns:
        The resolver.
    """
    return MinifyNameResolver(
        config=config, states_enabled=states, events_enabled=events, vars_enabled=vars
    )


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
    write_config(tmp_path, config)
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
