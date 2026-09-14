from __future__ import annotations

import asyncio

import pytest
from reflex_base.registry import RegistrationContext
from reflex_components_core.base.fragment import Fragment
from reflex_components_core.base.script import Script
from reflex_components_core.el.elements.metadata import Link

from reflex.compiler import utils
from reflex.compiler.utils import compile_state, create_document_root
from reflex.compiler.utils import write_file as compiler_write_file
from reflex.constants.state import FIELD_MARKER
from reflex.state import State
from reflex.utils.path_ops import write_file
from reflex.vars.base import computed_var


def test_write_file_reexport() -> None:
    """Existing compiler callers retain the shared file-writing helper."""
    assert compiler_write_file is write_file


def test_bundled_libraries_artifact_round_trip(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Backend-only workers can restore the registry from the frontend build."""
    monkeypatch.setattr(utils, "get_web_dir", lambda: tmp_path)
    with RegistrationContext() as context:
        context.bundled_libraries.append("@radix-ui/themes")
        output_path, output = utils._compile_bundled_libraries()
        artifact_path = tmp_path / output_path
        artifact_path.parent.mkdir()
        artifact_path.write_text(output, encoding="utf-8")
        context.bundled_libraries[:] = ["react"]

        utils._restore_bundled_libraries()

        assert context.bundled_libraries == [
            "react",
            "@emotion/react",
            "$/utils/context",
            "$/utils/state",
            "@radix-ui/themes",
        ]


def test_restore_bundled_libraries_preserves_page_registrations(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Restoring frontend metadata retains libraries discovered by page evaluation."""
    monkeypatch.setattr(utils, "get_web_dir", lambda: tmp_path)
    artifact_path = tmp_path / utils.constants.Dirs.BUNDLED_LIBRARIES
    artifact_path.parent.mkdir()
    artifact_path.write_text('["@radix-ui/themes"]', encoding="utf-8")
    with RegistrationContext() as context:
        context.bundled_libraries.append("page-library")

        utils._restore_bundled_libraries()

        assert "@radix-ui/themes" in context.bundled_libraries
        assert "page-library" in context.bundled_libraries


def test_restore_bundled_libraries_ignores_invalid_utf8(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Malformed registry artifacts do not interrupt backend-only startup."""
    monkeypatch.setattr(utils, "get_web_dir", lambda: tmp_path)
    artifact_path = tmp_path / utils.constants.Dirs.BUNDLED_LIBRARIES
    artifact_path.parent.mkdir()
    artifact_path.write_bytes(b"\xff")

    utils._restore_bundled_libraries()


@pytest.mark.parametrize(
    "contents",
    ["{", '"@radix-ui/themes"', '["@radix-ui/themes", 1]'],
)
def test_restore_bundled_libraries_ignores_invalid_json(
    tmp_path, monkeypatch: pytest.MonkeyPatch, contents: str
) -> None:
    """Malformed registry data does not change backend registrations."""
    monkeypatch.setattr(utils, "get_web_dir", lambda: tmp_path)
    artifact_path = tmp_path / utils.constants.Dirs.BUNDLED_LIBRARIES
    artifact_path.parent.mkdir()
    artifact_path.write_text(contents, encoding="utf-8")
    with RegistrationContext() as context:
        original = list(context.bundled_libraries)

        utils._restore_bundled_libraries()

        assert context.bundled_libraries == original


def test_restore_bundled_libraries_ignores_missing_artifact(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing frontend artifact does not interrupt backend-only startup."""
    monkeypatch.setattr(utils, "get_web_dir", lambda: tmp_path)

    utils._restore_bundled_libraries()


def test_document_preloads_the_global_stylesheet():
    """Render-blocking CSS should be discoverable alongside early resource hints."""
    head = create_document_root().children[0]
    links = [
        child.render()["props"] for child in head.children if isinstance(child, Link)
    ]
    preload = next(props for props in links if 'rel:"preload"' in props)
    stylesheet = next(props for props in links if 'rel:"stylesheet"' in props)
    assert next(prop for prop in preload if prop.startswith("href:")) == next(
        prop for prop in stylesheet if prop.startswith("href:")
    )
    assert 'as:"style"' in preload


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
