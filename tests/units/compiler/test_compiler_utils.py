from __future__ import annotations

import asyncio

import pytest
from reflex_components_core.base.fragment import Fragment
from reflex_components_core.base.script import Script

from reflex.compiler.utils import compile_state, create_document_root, write_file
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


def test_document_root_allows_static_id_on_head_script():
    """A head script's ID should remain an HTML attribute without a hook."""
    head_script = Script.create(src="/probe.js", id="head-probe")
    document_root = create_document_root(head_components=[head_script])

    rendered = str(document_root.render())
    assert not document_root._get_all_hooks()
    assert 'id:"head-probe"' in rendered
    assert "ref_head_probe" not in rendered
    assert head_script._get_all_hooks()
    assert "ref_head_probe" in str(head_script.render())


def test_document_root_literalizes_nested_ids_without_mutating_original():
    """Nested head IDs are literalized on a copy of the user component."""
    nested_script = Script.create(src="/probe.js", id="nested-probe")
    head_component = Fragment.create(nested_script)
    document_root = create_document_root(head_components=[head_component])

    rendered = str(document_root.render())
    assert not document_root._get_all_hooks()
    assert 'id:"nested-probe"' in rendered
    assert "ref_nested_probe" not in rendered
    assert head_component._get_all_hooks()
    assert nested_script._get_all_hooks()


def test_document_root_controls_preserve_no_id_and_page_refs():
    """IDs outside the document root keep their normal ref behavior."""
    document_root = create_document_root(
        head_components=[Script.create(src="/probe.js")]
    )
    page_script = Script.create(src="/probe.js", id="page-probe")

    assert not document_root._get_all_hooks()
    assert page_script._get_all_hooks()


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
