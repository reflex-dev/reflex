"""Global toggle for the frontend inspector.

The compile-time pass and the request-time backend run in separate
processes:

- ``reflex run`` does the full compile in a one-shot
  ``ProcessPoolExecutor`` subprocess so Granian's hot-reload watcher
  doesn't see an already-imported app module. ``start_compile`` (and
  therefore ``set_enabled``) only fires inside that subprocess, which
  exits before the orchestrator spawns the Granian worker.
- The orchestrator then drops a ``nocompile`` marker and spawns the
  Granian worker. The worker reads the marker, short-circuits compile,
  and never runs ``start_compile``.

So neither the orchestrator nor the worker observes the in-memory
``set_enabled(True)`` call, and ``os.environ`` writes made inside the
compile subprocess do not propagate back to its parent. The worker
therefore falls back to the on-disk artifact written by the compile
pass: the presence of ``source-map.json`` is the build's commitment to
ship inspector ids, so the worker should keep capturing.
``REFLEX_FRONTEND_INSPECTOR_ENABLED`` is honored as an explicit override
for tests and direct-spawn child processes that *do* inherit the parent's
environment.
"""

from __future__ import annotations

import os
from typing import Final

_ENV_KEY: Final = "REFLEX_FRONTEND_INSPECTOR_ENABLED"

# ``None`` means no explicit decision has been made yet; the first
# ``is_enabled()`` call resolves it against the env var or the on-disk
# artifact and latches the answer for the rest of the process.
_ENABLED: bool | None = None


def _source_map_exists() -> bool:
    try:
        from reflex_base import constants
        from reflex_base.environment import environment
        from reflex_base.inspector import PUBLIC_DIRNAME, SOURCE_MAP_FILENAME
    except ImportError:
        return False
    path = (
        environment.REFLEX_WEB_WORKDIR.get()
        / constants.Dirs.PUBLIC
        / PUBLIC_DIRNAME
        / SOURCE_MAP_FILENAME
    )
    try:
        return path.is_file()
    except OSError:
        return False


def _decide() -> bool:
    val = os.environ.get(_ENV_KEY)
    if val is not None:
        return val == "1"
    return _source_map_exists()


def set_enabled(on: bool) -> None:
    """Set whether the inspector is active.

    Enabling exports ``REFLEX_FRONTEND_INSPECTOR_ENABLED=1`` so any
    direct-spawn child process inherits the decision. Disabling clears
    the env var rather than writing ``"0"`` — writing a sentinel would
    leak across test fixtures and into every subprocess spawned later.

    Args:
        on: True to enable, False to disable.
    """
    global _ENABLED
    _ENABLED = on
    if on:
        os.environ[_ENV_KEY] = "1"
    else:
        os.environ.pop(_ENV_KEY, None)


def is_enabled() -> bool:
    """Return whether the inspector is currently active.

    Returns:
        True if the inspector should capture call sites and emit ``data-rx``.
    """
    global _ENABLED
    if _ENABLED is None:
        _ENABLED = _decide()
    return _ENABLED
