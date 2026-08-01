from __future__ import annotations

import asyncio

import pytest

from reflex.compiler.utils import compile_state, write_file
from reflex.constants.state import FIELD_MARKER
from reflex.state import State
from reflex.vars.base import computed_var


class CompileStateState(State):
    """State fixture exercising async computed vars during compile_state."""

    a: int = 1
    b: int = 2

    @computed_var
    async def async_value(self) -> str:
        """Return a resolved value after yielding to the event loop.

        Returns:
            The resolved string value.
        """
        await asyncio.sleep(0)
        return "resolved"


def _get_state_values(compiled: dict, state: type[State]) -> dict:
    return compiled[state.get_full_name()]


def test_compile_state_resolves_async_computed_vars_without_event_loop():
    compiled = compile_state(CompileStateState)
    values = _get_state_values(compiled, CompileStateState)
    assert values[f"a{FIELD_MARKER}"] == 1
    assert values[f"b{FIELD_MARKER}"] == 2
    assert values[f"async_value{FIELD_MARKER}"] == "resolved"


@pytest.mark.asyncio
async def test_compile_state_resolves_async_computed_vars_with_running_event_loop():
    assert asyncio.get_running_loop() is not None
    await asyncio.sleep(0)
    compiled = compile_state(CompileStateState)
    values = _get_state_values(compiled, CompileStateState)
    assert values[f"a{FIELD_MARKER}"] == 1
    assert values[f"b{FIELD_MARKER}"] == 2
    assert values[f"async_value{FIELD_MARKER}"] == "resolved"


def test_write_file_creates_and_updates(tmp_path):
    path = tmp_path / "sub" / "page.jsx"
    write_file(path, "v1")
    assert path.read_text() == "v1"
    write_file(path, "v2")
    assert path.read_text() == "v2"


def test_write_file_atomic_leaves_no_temp_files(tmp_path):
    path = tmp_path / "page.jsx"
    write_file(path, "content")
    # The temp file used for the atomic replace must not linger.
    assert [p.name for p in tmp_path.iterdir()] == ["page.jsx"]


def test_write_file_skips_byte_identical_write(tmp_path):
    """An identical write must not touch the file (so vite isn't told to HMR)."""
    path = tmp_path / "page.jsx"
    write_file(path, "same")
    before = path.stat().st_mtime_ns
    import os

    os.utime(path, ns=(before + 1_000_000_000, before + 1_000_000_000))
    bumped = path.stat().st_mtime_ns
    write_file(path, "same")  # identical -> no rewrite
    assert path.stat().st_mtime_ns == bumped
