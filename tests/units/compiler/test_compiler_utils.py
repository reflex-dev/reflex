from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path

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


@pytest.fixture(params=["relative", "absolute"])
def asset_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request):
    """Prepare an app with a relative or custom absolute frontend directory.

    Args:
        tmp_path: The temporary application directory.
        monkeypatch: Fixture for configuring paths.
        request: The frontend directory variant.

    Returns:
        The source assets and public output directories.
    """
    monkeypatch.chdir(tmp_path)
    web_dir = Path(".web") if request.param == "relative" else tmp_path / "custom-web"
    monkeypatch.setattr(utils, "get_web_dir", lambda: web_dir)
    assets = tmp_path / "assets"
    assets.mkdir()
    public = web_dir / "public"
    public.mkdir(parents=True)
    return assets, public


def test_sync_app_assets_renames_and_prunes_empty_directories(asset_project):
    """Renamed files replace old copies without deleting unrelated public files.

    Args:
        asset_project: The source and destination directories.
    """
    assets, public = asset_project
    (assets / "nested" / "empty").mkdir(parents=True)
    old = assets / "nested" / "empty" / "old.txt"
    old.write_text("asset")
    (public / "untracked.txt").write_text("generated before the first compile")
    utils._sync_app_assets()
    old.rename(assets / "new.txt")
    shutil.rmtree(assets / "nested")

    utils._sync_app_assets()

    assert not (public / "nested").exists()
    assert (public / "new.txt").read_text() == "asset"
    assert (
        public / "untracked.txt"
    ).read_text() == "generated before the first compile"
    assert list(
        json.loads((public.parent / utils._ASSET_MANIFEST_FILENAME).read_text())
    ) == ["new.txt"]
    assert not (public / utils._ASSET_MANIFEST_FILENAME).exists()


def test_sync_app_assets_preserves_incremental_copies(asset_project):
    """Unchanged assets and their manifest keep timestamps across compiles.

    Args:
        asset_project: The source and destination directories.
    """
    assets, public = asset_project
    source = assets / "keep.txt"
    source.write_text("original")
    utils._sync_app_assets()
    destination = public / source.name
    manifest = public.parent / utils._ASSET_MANIFEST_FILENAME
    old_time = source.stat().st_mtime_ns - 10_000_000_000
    os.utime(source, ns=(old_time, old_time))
    before = destination.stat(), manifest.stat()

    utils._sync_app_assets()

    assert destination.stat().st_mtime_ns == before[0].st_mtime_ns
    assert manifest.stat().st_mtime_ns == before[1].st_mtime_ns
    source.write_text("changed")
    new_time = before[0].st_mtime_ns + 10_000_000_000
    os.utime(source, ns=(new_time, new_time))
    utils._sync_app_assets()
    assert destination.read_text() == "changed"


def test_sync_app_assets_scan_failure_preserves_copies(
    asset_project, monkeypatch: pytest.MonkeyPatch
):
    """Unreadable source directories must not be treated as deleted assets.

    Args:
        asset_project: The source and destination directories.
        monkeypatch: Fixture for simulating an unreadable directory.
    """
    assets, public = asset_project
    nested = assets / "nested"
    nested.mkdir()
    (nested / "asset.txt").write_text("keep")
    utils._sync_app_assets()
    manifest = public.parent / utils._ASSET_MANIFEST_FILENAME
    previous_manifest = manifest.read_bytes()
    scandir = os.scandir

    def unreadable_scandir(path):
        """Fail when listing the nested source directory.

        Args:
            path: The directory being listed.

        Returns:
            The directory iterator for readable directories.

        Raises:
            PermissionError: When listing the nested source directory.
        """
        if Path(path).resolve() == nested:
            msg = "unreadable assets"
            raise PermissionError(msg)
        return scandir(path)

    monkeypatch.setattr(os, "scandir", unreadable_scandir)
    with pytest.raises(PermissionError, match="unreadable assets"):
        utils._sync_app_assets()

    assert (public / "nested" / "asset.txt").read_text() == "keep"
    assert manifest.read_bytes() == previous_manifest


@pytest.mark.parametrize("start_with_directory", [False, True])
def test_sync_app_assets_changes_file_type(asset_project, start_with_directory: bool):
    """An app asset may change between a file and a directory.

    Args:
        asset_project: The source and destination directories.
        start_with_directory: Whether the original asset is a directory.
    """
    assets, public = asset_project
    source = assets / "asset"
    if start_with_directory:
        source.mkdir()
        (source / "child.txt").write_text("old")
    else:
        source.write_text("old")
    utils._sync_app_assets()
    if start_with_directory:
        shutil.rmtree(source)
        source.write_text("new")
    else:
        source.unlink()
        source.mkdir()
        (source / "child.txt").write_text("new")

    utils._sync_app_assets()

    destination = public / "asset"
    if not start_with_directory:
        destination /= "child.txt"
    assert destination.read_text() == "new"


@pytest.mark.parametrize(
    "contents",
    [
        None,
        "not json",
        "{}",
        '[1, "../outside.txt", "", "."]',
        '["untracked.txt"]',
        '{"untracked.txt": 42}',
    ],
)
def test_sync_app_assets_without_valid_ownership_preserves_public_files(
    asset_project, contents: str | None
):
    """Missing or corrupt ownership data never claims existing public files.

    Args:
        asset_project: The source and destination directories.
        contents: Optional invalid manifest content.
    """
    assets, public = asset_project
    manifest = public.parent / utils._ASSET_MANIFEST_FILENAME
    (public / "untracked.txt").write_text("keep")
    outside = public.parent / "outside.txt"
    outside.write_text("outside")
    if contents is not None:
        manifest.write_text(contents)
    (assets / "tracked.txt").write_text("asset")

    utils._sync_app_assets()
    shutil.rmtree(assets)
    utils._sync_app_assets()

    assert not (public / "tracked.txt").exists()
    assert (public / "untracked.txt").read_text() == "keep"
    assert outside.read_text() == "outside"


def test_sync_app_assets_preserves_directory_replacing_a_copy(asset_project):
    """Removing a tracked file never recursively deletes a generated directory.

    Args:
        asset_project: The source and destination directories.
    """
    assets, public = asset_project
    (assets / "asset").write_text("old")
    utils._sync_app_assets()
    (assets / "asset").unlink()
    destination = public / "asset"
    destination.unlink()
    destination.mkdir()
    (destination / "generated.txt").write_text("keep")

    utils._sync_app_assets()

    assert (destination / "generated.txt").read_text() == "keep"


@pytest.mark.parametrize("intermediate_compiles", [0, 2])
@pytest.mark.parametrize("replacement", ["content", "same_metadata", "same_content"])
def test_sync_app_assets_preserves_replaced_copy(
    asset_project, intermediate_compiles: int, replacement: str
):
    """A plugin replacement must not be deleted or adopted by later compiles.

    Args:
        asset_project: The source and destination directories.
        intermediate_compiles: Compiles while both source and replacement exist.
        replacement: Whether the replacement retains the original metadata or bytes.
    """
    assets, public = asset_project
    source = assets / "shared.txt"
    source.write_bytes(b"app original")
    utils._sync_app_assets()
    destination = public / source.name
    original_stat = destination.stat()
    content = b"app original" if replacement == "same_content" else b"plugin asset"
    destination.write_bytes(content)
    mtime = original_stat.st_mtime_ns
    if replacement != "same_metadata":
        mtime += 10_000_000_000
    os.utime(destination, ns=(mtime, mtime))
    for _ in range(intermediate_compiles):
        utils._sync_app_assets()
    source.unlink()

    utils._sync_app_assets()

    assert destination.read_bytes() == content


@pytest.mark.parametrize("existing_copy", [False, True])
def test_sync_app_assets_initial_ownership_comes_from_source(
    asset_project, existing_copy: bool
):
    """Adopt existing app copies without claiming skipped plugin output.

    Args:
        asset_project: The source and destination directories.
        existing_copy: Whether public contains a prior app copy or a plugin file.
    """
    assets, public = asset_project
    source = assets / "shared.txt"
    source.write_text("app")
    destination = public / source.name
    shutil.copy2(source, destination)
    if not existing_copy:
        destination.write_text("plugin")
        mtime = source.stat().st_mtime_ns + 10_000_000_000
        os.utime(destination, ns=(mtime, mtime))
    utils._sync_app_assets()
    source.unlink()

    utils._sync_app_assets()

    if existing_copy:
        assert not destination.exists()
    else:
        assert destination.read_text() == "plugin"


@pytest.mark.parametrize("copy_update", [False, True])
def test_sync_app_assets_tracks_the_last_actual_copy(asset_project, copy_update: bool):
    """Source changes only replace the ownership fingerprint when copied.

    Args:
        asset_project: The source and destination directories.
        copy_update: Whether the source change is newer than the destination.
    """
    assets, public = asset_project
    source = assets / "asset.txt"
    source.write_text("original")
    utils._sync_app_assets()
    destination = public / source.name
    source.write_text("updated")
    mtime = destination.stat().st_mtime_ns
    mtime += 10_000_000_000 if copy_update else -10_000_000_000
    os.utime(source, ns=(mtime, mtime))
    utils._sync_app_assets()
    assert destination.read_text() == ("updated" if copy_update else "original")
    source.unlink()

    utils._sync_app_assets()

    assert not destination.exists()


def test_sync_app_assets_follows_source_symlinks(asset_project, windows_platform: bool):
    """Shared assets copied through symlinks are removed when their links disappear.

    Args:
        asset_project: The source and destination directories.
        windows_platform: Whether symlinks require Windows privileges.
    """
    if windows_platform:
        pytest.skip("Symlinks require additional privileges on Windows")
    assets, public = asset_project
    shared = assets.parent / "shared"
    shared.mkdir()
    (shared / "file.txt").write_text("shared")
    (assets / "directory").symlink_to(shared, target_is_directory=True)
    (assets / "file.txt").symlink_to(shared / "file.txt")
    utils._sync_app_assets()
    assert (public / "directory" / "file.txt").read_text() == "shared"
    assert (public / "file.txt").read_text() == "shared"
    (assets / "directory").unlink()
    (shared / "file.txt").unlink()

    utils._sync_app_assets()

    assert not (public / "directory").exists()
    assert not (public / "file.txt").exists()
    assert shared.is_dir()


def test_sync_app_assets_preserves_symlink_replacing_a_copy(
    asset_project, windows_platform: bool
):
    """A new symlink is not the owned copy even if its target still matches.

    Args:
        asset_project: The source and destination directories.
        windows_platform: Whether symlinks require Windows privileges.
    """
    if windows_platform:
        pytest.skip("Symlinks require additional privileges on Windows")
    assets, public = asset_project
    source = assets / "asset.txt"
    source.write_text("asset")
    utils._sync_app_assets()
    destination = public / source.name
    target = assets.parent / "generated.txt"
    shutil.copy2(destination, target)
    destination.unlink()
    destination.symlink_to(target)
    source.unlink()

    utils._sync_app_assets()

    assert destination.is_symlink()
    assert target.read_text() == "asset"


@pytest.mark.parametrize("outside_public", [False, True])
def test_sync_app_assets_does_not_prune_through_symlinks(
    asset_project, windows_platform: bool, outside_public: bool
):
    """Cleanup cannot follow a replaced public directory to another file.

    Args:
        asset_project: The source and destination directories.
        windows_platform: Whether symlinks require Windows privileges.
        outside_public: Whether the symlink points outside the public directory.
    """
    if windows_platform:
        pytest.skip("Symlinks require additional privileges on Windows")
    assets, public = asset_project
    (assets / "nested").mkdir()
    (assets / "nested" / "asset.txt").write_text("old")
    utils._sync_app_assets()
    generated = (assets.parent if outside_public else public) / "generated"
    generated.mkdir()
    shutil.copy2(public / "nested" / "asset.txt", generated / "asset.txt")
    shutil.rmtree(assets)
    shutil.rmtree(public / "nested")
    (public / "nested").symlink_to(generated.resolve(), target_is_directory=True)

    utils._sync_app_assets()

    assert (generated / "asset.txt").read_text() == "old"


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
