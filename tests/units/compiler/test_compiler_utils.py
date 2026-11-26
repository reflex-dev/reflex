from __future__ import annotations

import asyncio
import importlib
import json
import os
import shutil
import sys
from collections.abc import Generator
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Annotated, Literal, TypedDict

import pytest
from reflex_base import constants
from reflex_base.components.memo import create_passthrough_component_memo
from reflex_base.js.modules import _app_modules, _load_module
from reflex_base.registry import RegistrationContext
from reflex_base.utils.exceptions import ReflexRuntimeError
from reflex_components_core.base.fragment import Fragment
from reflex_components_core.base.script import Script
from reflex_components_core.el.elements.metadata import Link
from reflex_components_core.el.elements.typography import Div

import reflex as rx
from reflex.compiler import utils
from reflex.compiler.utils import compile_state, create_document_root
from reflex.compiler.utils import write_file as compiler_write_file
from reflex.constants.state import FIELD_MARKER
from reflex.state import State, state_snapshot_hashes
from reflex.utils.exceptions import VarTypeError
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
    with pytest.raises(PermissionError) as error:
        utils._sync_app_assets()

    assert str(error.value) == "unreadable assets"
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
@pytest.mark.parametrize("replacement", ["content", "same_mtime", "same_content"])
def test_sync_app_assets_preserves_replaced_copy(
    asset_project, intermediate_compiles: int, replacement: str
):
    """A plugin replacement must not be deleted or adopted by later compiles.

    Args:
        asset_project: The source and destination directories.
        intermediate_compiles: Compiles while both source and replacement exist.
        replacement: Whether the replacement retains the original mtime or bytes.
    """
    assets, public = asset_project
    source = assets / "shared.txt"
    source.write_bytes(b"app original")
    utils._sync_app_assets()
    destination = public / source.name
    original_stat = destination.stat()
    content = b"app original" if replacement == "same_content" else b"plugin"
    destination.write_bytes(content)
    mtime = original_stat.st_mtime_ns
    if replacement != "same_mtime":
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


def test_memo_root_prop_forwarding_preserves_cached_analysis() -> None:
    """Repeated emission of shared memo bodies must not accumulate prop merges."""
    with RegistrationContext.ensure_context().fork() as context:
        _, first = create_passthrough_component_memo(Div.create("first", id="root"))
        _, second = create_passthrough_component_memo(Div.create("second", id="root"))
        assert first.export_name == second.export_name
        analysis = context._memo_body_analyses[
            first.component.__dict__["_memo_analysis_key"]
        ]
        original_render = deepcopy(analysis.rendered)

        for definition in (first, first, second):
            compiled, _ = utils.compile_experimental_component_memo(definition)
            props = ", ".join(compiled["render"]["props"])
            assert props.count("mergeSlotProps(") == 1
            assert "ref:ref_root" in props
            assert analysis.rendered == original_render


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
            f"$/{constants.Dirs.UTILS}/context-registry",
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


def _global_stylesheet_links() -> list[list[str]]:
    """Render the framework link tags of a fresh document head.

    Returns:
        The rendered props of every ``Link`` in the head.
    """
    head = create_document_root().children[0]
    return [
        child.render()["props"] for child in head.children if isinstance(child, Link)
    ]


def test_document_preloads_the_global_stylesheet_in_prod(
    monkeypatch: pytest.MonkeyPatch,
):
    """Production builds hint the render-blocking CSS ahead of the stylesheet link.

    Args:
        monkeypatch: Selects prod mode and restores the previous mode afterwards.
    """
    monkeypatch.setenv("REFLEX_ENV_MODE", constants.Env.PROD.value)
    links = _global_stylesheet_links()
    preload = next(props for props in links if 'rel:"preload"' in props)
    stylesheet = next(props for props in links if 'rel:"stylesheet"' in props)
    assert next(prop for prop in preload if prop.startswith("href:")) == next(
        prop for prop in stylesheet if prop.startswith("href:")
    )
    assert 'as:"style"' in preload


def test_document_does_not_preload_the_global_stylesheet_in_dev(
    monkeypatch: pytest.MonkeyPatch,
):
    """Dev builds link the stylesheet once so Vite's css-update swaps that link.

    Args:
        monkeypatch: Selects dev mode and restores the previous mode afterwards.
    """
    monkeypatch.setenv("REFLEX_ENV_MODE", constants.Env.DEV.value)
    links = _global_stylesheet_links()
    assert not any('rel:"preload"' in props for props in links)
    assert sum('rel:"stylesheet"' in props for props in links) == 1


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


def test_compile_state_hashes_dict_with_mixed_key_types(
    forked_registration_context: RegistrationContext,
):
    """A dict default mixing int and str keys compiles and hashes without comparing keys.

    Args:
        forked_registration_context: Keeps the test's state out of other tests.
    """

    class MixedKeyState(State):
        mapping: dict[str | int, str] = {1: "one", "two": "two"}

    compiled = compile_state(MixedKeyState)
    assert _get_state_values(compiled, MixedKeyState) == {
        f"mapping{FIELD_MARKER}": {1: "one", "two": "two"}
    }
    assert len(state_snapshot_hashes(compiled)) == len(compiled) + 1


@pytest.mark.parametrize(
    "annotation",
    [rx.Cookie, rx.LocalStorage, rx.SessionStorage],
    ids=lambda t: t.__name__,
)
def test_compile_client_storage_rejects_factory_on_storage_annotation(
    annotation: type,
    forked_registration_context: RegistrationContext,
):
    """A browser storage var annotated with a storage type takes no default_factory.

    Args:
        annotation: The browser storage type the var is annotated with.
        forked_registration_context: Keeps the test's state out of other tests.
    """
    # Built with type() so the annotation is the parametrized storage type.
    StorageState = type(
        "StorageState",
        (State,),
        {
            "__module__": __name__,
            "__qualname__": "test_rejects_factory_on_storage_annotation.<locals>.StorageState",
            "__annotations__": {"value": annotation},
            "value": rx.field(default_factory=lambda: annotation("new", name="key")),
        },
    )

    with pytest.raises(VarTypeError, match=r"\.value' cannot use a default_factory"):
        utils.compile_client_storage(StorageState)


def test_compile_client_storage_rejects_factory_on_set_default(
    forked_registration_context: RegistrationContext,
):
    """set_default with a default_factory is rejected on a browser storage var.

    Args:
        forked_registration_context: Keeps the test's state out of other tests.
    """

    class StorageState(State):
        value: rx.LocalStorage = rx.LocalStorage("declared", name="storage-key")

    StorageState.__fields__["value"].set_default(
        default_factory=lambda: rx.LocalStorage("new", name="storage-key")
    )
    with pytest.raises(VarTypeError, match=r"\.value' cannot use a default_factory"):
        utils.compile_client_storage(StorageState)


def test_compile_client_storage_rejects_factory_producing_storage(
    forked_registration_context: RegistrationContext,
):
    """A plain-annotated var whose default_factory produces browser storage is rejected.

    Args:
        forked_registration_context: Keeps the test's state out of other tests.
    """

    class StorageState(State):
        theme: rx.Field[str] = rx.field(
            default_factory=lambda: rx.LocalStorage("light", name="theme")
        )

    class OptionalStorageState(State):
        theme: rx.Field[str | None] = rx.field(
            default_factory=lambda: rx.LocalStorage("light", name="theme")
        )

    class OptionalAnnotatedStorageState(State):
        theme: rx.Field[rx.LocalStorage | None] = rx.field(
            default_factory=lambda: rx.LocalStorage("light", name="theme")
        )

    class LiteralStorageState(State):
        theme: rx.Field[Literal["light", "dark"]] = rx.field(  # pyright: ignore[reportAssignmentType]
            default_factory=lambda: rx.LocalStorage("light", name="theme")
        )

    class MetadataStorageState(State):
        theme: rx.Field[Annotated[str, "meta"]] = rx.field(
            default_factory=lambda: rx.LocalStorage("light", name="theme")
        )

    for state in (
        StorageState,
        OptionalStorageState,
        OptionalAnnotatedStorageState,
        LiteralStorageState,
        MetadataStorageState,
    ):
        with pytest.raises(
            VarTypeError, match=r"\.theme' cannot use a default_factory"
        ):
            utils.compile_client_storage(state)


class Node(TypedDict):
    """A typed dict default, which issubclass refuses to check."""

    name: str


def test_compile_client_storage_skips_plain_factories(
    forked_registration_context: RegistrationContext,
):
    """A default_factory producing a plain value compiles as an ordinary var.

    Args:
        forked_registration_context: Keeps the test's state out of other tests.
    """
    calls = []

    def make_text() -> str:
        """Record the call and return a plain default.

        Returns:
            The default text.
        """
        calls.append(1)
        return "plain"

    def missing_at_compile() -> str:
        """Fail: a factory that only works at runtime is skipped while compiling.

        Raises:
            RuntimeError: Always.
        """
        msg = "only available at runtime"
        raise RuntimeError(msg)

    class PlainState(State):
        text: rx.Field[str] = rx.field(default_factory=make_text)
        _token: rx.Field[str] = rx.field(default_factory=missing_at_compile)
        runtime_only: rx.Field[str] = rx.field(default_factory=missing_at_compile)
        items: rx.Field[list[str]] = rx.field(default_factory=list)
        # issubclass against a TypedDict raises, so the check must not ask it.
        node: rx.Field[Node] = rx.field(default_factory=lambda: Node(name="root"))
        local: str = rx.LocalStorage("declared", name="local-key")

    compiled = utils.compile_client_storage(PlainState)
    name = PlainState.get_full_name()
    assert compiled[constants.LOCAL_STORAGE] == {
        f"{name}.local{FIELD_MARKER}": {"name": "local-key", "sync": False}
    }
    assert compiled[constants.COOKIES] == compiled[constants.SESSION_STORAGE] == {}
    assert calls == [1]


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


@pytest.fixture
def script_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clean_registration_context: RegistrationContext,
) -> Generator[tuple[Path, dict, list[list[Path]]], None, None]:
    """An app package that imports JavaScript modules, read by a stand-in script.

    Args:
        tmp_path: pytest tmp_path fixture.
        monkeypatch: pytest monkeypatch fixture.
        clean_registration_context: a fresh registry for the app's config.

    Yields:
        The package's directory, the output of the stand-in, which the test
        fills (it starts with no link loops), and the paths each of its runs
        read.
    """
    clean_registration_context._set_config(rx.Config(app_name="app"))
    monkeypatch.setattr(utils, "get_web_dir", lambda: tmp_path / ".web")
    monkeypatch.syspath_prepend(str(tmp_path))
    report: dict = {"loops": []}
    runs: list[list[Path]] = []

    def read_script_modules(paths: list[Path]) -> dict:
        """Record the paths of a run, and print the report the test fills.

        Args:
            paths: The modules.

        Returns:
            The report.
        """
        runs.append(paths)
        return report

    monkeypatch.setattr(utils, "_read_script_modules", read_script_modules)
    yield tmp_path.resolve() / "app", report, runs
    for name in [n for n in sys.modules if n.partition(".")[0] == "app"]:
        del sys.modules[name]


def _import_script_module(
    monkeypatch: pytest.MonkeyPatch, name: str, path: Path, names: set[str]
) -> None:
    """Put a JavaScript module in sys.modules, as importing it does.

    Args:
        monkeypatch: pytest monkeypatch fixture, which removes it afterwards.
        name: The module's name.
        path: Its file.
        names: The names Python uses from it.
    """
    module = ModuleType(name)
    _load_module(module, path)
    for function in names:
        getattr(module, function)
    monkeypatch.setitem(sys.modules, name, module)


def _script_exports(
    files: list[Path],
    functions: list[str],
    values: list[str] | None = None,
    exports_all: bool = False,
) -> dict:
    """Build what script-modules.js reads of a module.

    Args:
        files: The module and the files it reaches.
        functions: Its functions.
        values: Its values.
        exports_all: Whether it re-exports another module's names.

    Returns:
        The module's entry in the script's output.
    """
    return {
        "files": [str(file) for file in files],
        "functions": functions,
        "values": values or [],
        "exportsAll": exports_all,
    }


def test_compile_script_modules(
    script_app: tuple[Path, dict, list[list[Path]]],
    monkeypatch: pytest.MonkeyPatch,
):
    """Modules are indexed through a link to the app's package, and stubbed.

    Args:
        script_app: the app package, the stand-in script's output and its runs.
        monkeypatch: pytest monkeypatch fixture.
    """
    package, report, runs = script_app
    # The directory the link points to; the modules' files are never read.
    package.mkdir()
    web_dir = utils.get_web_dir()
    party = package / "scripts" / "party.js"
    helpers = package / "scripts" / "helpers.js"
    css = package / "scripts" / "party.css"
    typed = package / "typed.ts"
    # Only importlib can import a module whose name is not an identifier.
    widget = package / 'my-"widget".js'
    _import_script_module(monkeypatch, "app.typed", typed, {"typed", "fromStar"})
    _import_script_module(monkeypatch, "app.scripts.party", party, {"celebrate"})
    _import_script_module(monkeypatch, 'app.my-"widget"', widget, {"show"})
    # Another app's module, imported earlier in the process, is left out.
    _import_script_module(monkeypatch, "other.party", party, {"celebrate"})
    report.update({
        "modules": {
            str(party): _script_exports([party, helpers, css], ["celebrate"]),
            # `fromStar` may come from its `export * from`.
            str(typed): _script_exports([typed], ["typed"], exports_all=True),
            str(widget): _script_exports([widget, helpers], ["show", "$private"]),
        },
        "imports": {
            str(party): ["canvas-confetti", "$/utils/reflex"],
            str(helpers): ["dayjs", "canvas-confetti?x"],
            str(typed): [],
            str(widget): [],
        },
        "errors": [],
    })

    outputs, package_imports = utils.compile_script_modules(_app_modules())

    assert runs == [[widget, party, typed]]
    # A symbolic link, or a junction on Windows.
    assert (web_dir / "utils" / "script_modules" / "app").resolve() == package

    def stub(name: str, function: str) -> str:
        """Render the stub of a module that exports one function.

        Args:
            name: The module's file name.
            function: The function.

        Returns:
            The stub.
        """
        return (
            f"# Generated by Reflex from {name}; rewritten when it changes.\n"
            "from typing import Any\n"
            "\n"
            "from reflex_base.event import EventSpec\n"
            "\n"
            f"def {function}(*args: Any) -> EventSpec: ...\n"
        )

    assert outputs == [
        (str(package / 'my-"widget".pyi'), stub('my-"widget".js', "show")),
        (str(package / "scripts" / "party.pyi"), stub("party.js", "celebrate")),
        (str(package / "typed.pyi"), stub("typed.ts", "typed")),
        (
            str(web_dir / "utils" / "scripts.js"),
            (
                "export default {\n"
                '  "app.my-\\"widget\\"": () => import("$/utils/script_modules/app/my-\\"widget\\".js"),\n'
                '  "app.scripts.party": () => import("$/utils/script_modules/app/scripts/party.js"),\n'
                '  "app.typed": () => import("$/utils/script_modules/app/typed.ts"),\n'
                "};\n"
            ),
        ),
    ]
    assert package_imports == {
        "canvas-confetti": [rx.ImportVar(tag=None, render=False)],
        "dayjs": [rx.ImportVar(tag=None, render=False)],
    }


@pytest.mark.parametrize(
    ("names", "files", "functions", "errors", "message"),
    [
        (
            {"celebrate"},
            ["app/scripts/party.js"],
            ["celebrate"],
            [
                {
                    "file": "<helpers>",
                    "line": 3,
                    "column": 7,
                    "message": "Unexpected token",
                }
            ],
            (
                "Syntax error at <helpers>:3:7: Unexpected "
                "token. Fix the code there: the app imports this file from Python, "
                "directly or through another JavaScript module."
            ),
        ),
        (
            {"celebrate", "nope"},
            ["app/scripts/party.js"],
            ["celebrate", "launch"],
            [],
            (
                "`nope` is used from app.scripts.party, but <party> exports no "
                "function named nope (its functions: celebrate, launch). Export it "
                "from <party>, as in `export function nope() "
                "{ ... }`, or correct the name in Python."
            ),
        ),
        (
            {"limit"},
            ["app/scripts/party.js"],
            [],
            [],
            (
                "`limit` is used from app.scripts.party as a function, but <party> "
                "exports limit as a value, and Python can only call functions. "
                "Export a function instead, as in `export function "
                "limit() { ... }`."
            ),
        ),
        (
            {"celebrate"},
            # In the project, beside the package, but not in it.
            ["app/scripts/party.js", ".env"],
            ["celebrate"],
            [],
            (
                "The JavaScript module app.scripts.party imports <env>, which is "
                "outside <package>, the directory of the app's package, "
                "and only that directory is linked into the compiled app. Move the "
                "file into it, or publish it as an npm package and import it by name."
            ),
        ),
    ],
)
def test_compile_script_modules_errors(
    script_app: tuple[Path, dict, list[list[Path]]],
    monkeypatch: pytest.MonkeyPatch,
    names: set[str],
    files: list[str],
    functions: list[str],
    errors: list[dict],
    message: str,
):
    """A syntax error, a name not exported as a function, a file outside the package.

    Args:
        script_app: the app package, the stand-in script's output and its runs.
        monkeypatch: pytest monkeypatch fixture.
        names: the names Python uses.
        files: the files the module reaches, from the project's directory.
        functions: the module's functions.
        errors: the syntax errors.
        message: the expected error, with placeholders for the paths it names.
    """
    package, report, _ = script_app
    party = package / "scripts" / "party.js"
    # Each path as the platform writes it.
    paths = {
        "<helpers>": str(package / "scripts" / "helpers.js"),
        "<party>": str(Path("app", "scripts", "party.js")),
        "<env>": str(package.parent / ".env"),
        "<package>": str(package),
    }

    def fill(text: str) -> str:
        """Replace the path placeholders of an expected message.

        Args:
            text: The message, with placeholders.

        Returns:
            The message, with the paths.
        """
        for placeholder, path in paths.items():
            text = text.replace(placeholder, path)
        return text

    _import_script_module(monkeypatch, "app.scripts.party", party, names)
    report.update({
        "modules": {
            str(party): _script_exports(
                [package.parent / file for file in files], functions, ["limit"]
            )
        },
        "imports": {},
        "errors": [{**error, "file": fill(error["file"])} for error in errors],
    })
    with pytest.raises(ReflexRuntimeError) as error:
        utils.compile_script_modules(_app_modules())
    assert str(error.value) == fill(message)


def test_compile_script_modules_rejects_a_link_loop(
    script_app: tuple[Path, dict, list[list[Path]]],
    monkeypatch: pytest.MonkeyPatch,
):
    """A file that reaches itself again through a directory link names the link and how to avoid it.

    Args:
        script_app: the app package, the stand-in script's output and its runs.
        monkeypatch: pytest monkeypatch fixture.
    """
    package, report, _ = script_app
    party = package / "scripts" / "party.js"
    link = package / "scripts" / "loop"
    _import_script_module(monkeypatch, "app.scripts.party", party, {"celebrate"})
    report.update({
        "modules": {str(party): _script_exports([party], ["celebrate"])},
        "imports": {},
        "errors": [],
        "loops": [
            {"importer": str(party), "file": str(link / "party.js"), "link": str(link)}
        ],
    })
    with pytest.raises(ReflexRuntimeError) as error:
        utils.compile_script_modules(_app_modules())
    assert str(error.value) == (
        f"The JavaScript file {party} imports {link / 'party.js'} through {link}, "
        "a link back to a directory its imports were already in, so the bundler "
        "would import the same files again one link deeper, without end. Import "
        f"the file by a path that does not go through {link}, or replace {link} "
        "with a real directory."
    )


@pytest.mark.parametrize("linked", ["module", "import"])
def test_compile_script_modules_reads_links_where_they_are(
    script_app: tuple[Path, dict, list[list[Path]]],
    monkeypatch: pytest.MonkeyPatch,
    windows_platform: bool,
    linked: str,
):
    """A module, or a file it imports, that links outside the package is read where it is.

    The bundler does not follow links, so a link in the package is inside it.

    Args:
        script_app: the app package, the stand-in script's output and its runs.
        monkeypatch: pytest monkeypatch fixture.
        windows_platform: Whether symlinks require Windows privileges.
        linked: whether the module or the file it imports is the link.
    """
    if windows_platform:
        pytest.skip("Symlinks require additional privileges on Windows")
    package, report, runs = script_app
    shared = package.parent / "shared" / "vendor.js"
    shared.parent.mkdir()
    shared.write_text("export function shout() {}\n")
    vendor = package / "scripts" / "vendor.js"
    vendor.parent.mkdir(parents=True)
    vendor.symlink_to(shared)
    if linked == "module":
        name, files = "app.scripts.vendor", [vendor]
    else:
        name, files = "app.scripts.party", [package / "scripts" / "party.js", vendor]
    _import_script_module(monkeypatch, name, files[0], {"shout"})
    report.update({
        "modules": {str(files[0]): _script_exports(files, ["shout"])},
        "imports": {},
        "errors": [],
    })
    outputs, _ = utils.compile_script_modules(_app_modules())
    assert runs == [[files[0]]]
    specifier = Path("$/utils/script_modules", files[0].relative_to(package.parent))
    assert outputs[-1][1] == (
        f'export default {{\n  "{name}": () => import("{specifier.as_posix()}"),\n}};\n'
    )


def test_compile_script_modules_reads_a_module_imported_in_another_context(
    script_app: tuple[Path, dict, list[list[Path]]],
):
    """A module imported once compiles, with its names, into every later compile.

    Python runs a module once per process, so compiling the app again in a new
    registration context, as AppHarness does for each app, imports nothing anew.

    Args:
        script_app: the app package, the stand-in script's output and its runs.
    """
    package, report, runs = script_app
    package.mkdir()
    (package / "__init__.py").write_text("")
    party = package / "party.js"
    party.write_text("export function launch() {}\n")
    importlib.import_module("app.party").celebrate
    report.update({
        "modules": {str(party): _script_exports([party], ["launch"])},
        "imports": {str(party): []},
        "errors": [],
    })
    with RegistrationContext() as context:
        context._set_config(rx.Config(app_name="app"))
        with pytest.raises(ReflexRuntimeError) as error:
            utils.compile_script_modules(_app_modules())
    assert runs == [[party]]
    shown = Path("app", "party.js")
    assert str(error.value) == (
        f"`celebrate` is used from app.party, but {shown} exports no function "
        f"named celebrate (its functions: launch). Export it from {shown}, as "
        "in `export function celebrate() { ... }`, or correct the name in Python."
    )


def test_compile_script_modules_without_modules(
    script_app: tuple[Path, dict, list[list[Path]]],
):
    """An app that imports no JavaScript module gets an empty index, and runs no script.

    Args:
        script_app: the app package, the stand-in script's output and its runs.
    """
    _, _, runs = script_app
    assert utils.compile_script_modules({}) == (
        [(str(utils.get_web_dir() / "utils" / "scripts.js"), "export default {};\n")],
        {},
    )
    assert runs == []


# The reflex-frontend package, whose src/ is the web template in a checkout.
FRONTEND_PACKAGE = constants.Templates.Dirs.WEB_TEMPLATE.parent


def _require_node(*, packages: bool = False) -> None:
    """Skip a test that runs Node.js, or the frontend's scripts, without them.

    CI installs both and sets REFLEX_TEST_REQUIRE_FRONTEND, so that a missing
    one fails the test there instead.

    Args:
        packages: Whether the test also needs the frontend package's
            dependencies, which ``npm --prefix packages/reflex-frontend ci``
            installs.
    """
    node_modules = FRONTEND_PACKAGE / "node_modules"
    if shutil.which("node") and (not packages or (node_modules / "vite").is_dir()):
        return
    message = "Node.js is unavailable" + (
        f", or {node_modules} is not installed" if packages else ""
    )
    if os.environ.get("REFLEX_TEST_REQUIRE_FRONTEND"):
        pytest.fail(message)
    pytest.skip(message)


def _write_stand_in(web_dir: Path, output: str) -> None:
    """Write a stand-in for script-modules.js that prints the given output.

    Args:
        web_dir: The web directory.
        output: The JavaScript expression whose value it prints.
    """
    (web_dir / "script-modules.js").write_text(f"process.stdout.write({output});\n")


def test_read_script_modules_without_a_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Without Node.js or Bun to run the script, the error names both.

    Args:
        tmp_path: pytest tmp_path fixture.
        monkeypatch: pytest monkeypatch fixture.
    """
    monkeypatch.setattr(utils, "get_web_dir", lambda: tmp_path)
    monkeypatch.setattr(utils.path_ops, "get_node_path", lambda: None)
    monkeypatch.setattr(utils.path_ops, "get_bun_path", lambda: None)
    with pytest.raises(FileNotFoundError) as error:
        utils._read_script_modules([Path("/app/a.js")])
    assert str(error.value) == (
        "Node.js or Bun not found: Reflex runs one to read the JavaScript modules "
        "the app imports from Python. You might need to rerun `reflex init` or "
        "install either."
    )


def test_read_script_modules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The script runs in .web on the modules, and its failure says how to recover.

    Args:
        tmp_path: pytest tmp_path fixture.
        monkeypatch: pytest monkeypatch fixture.
    """
    _require_node()
    web_dir = tmp_path.resolve()
    monkeypatch.setattr(utils, "get_web_dir", lambda: web_dir)
    _write_stand_in(
        web_dir,
        "JSON.stringify({ format: 1, modules: {}, errors: [], loops: [],\n"
        "  imports: { [process.cwd()]: process.argv.slice(2) } })",
    )
    paths = [Path("/app/a.js"), Path("/app/b.ts")]
    assert utils._read_script_modules(paths) == {
        "format": 1,
        "modules": {},
        "imports": {str(web_dir): [str(path) for path in paths]},
        "errors": [],
        "loops": [],
    }
    (web_dir / "script-modules.js").write_text(
        'process.stderr.write("Error: boom\\n"); process.exit(3);\n'
    )
    with pytest.raises(ReflexRuntimeError) as error:
        utils._read_script_modules([Path("/app/a.js")])
    assert str(error.value) == (
        "Reflex could not read the JavaScript modules the app imports from "
        "Python: script-modules.js failed. If this repeats, delete "
        f"{web_dir / 'node_modules'} so that the next run reinstalls the "
        "frontend packages, or report the error at "
        "https://github.com/reflex-dev/reflex/issues:\nError: boom"
    )


@pytest.mark.parametrize(
    "output",
    [
        # Not JSON.
        '"Debugger attached."',
        # The output of another version of the script.
        "JSON.stringify({ modules: {}, imports: {}, errors: [] })",
        "JSON.stringify({ format: 2, modules: {}, imports: {}, errors: [] })",
        # The right version, of another shape.
        "JSON.stringify({ format: 1, modules: {}, imports: {}, loops: [] })",
        "JSON.stringify({ format: 1, modules: {}, imports: {}, errors: [] })",
        (
            "JSON.stringify({ format: 1, imports: {}, errors: [], loops: [],\n"
            '  modules: { "/app/a.js": { files: [1], functions: [], values: [],\n'
            "    exportsAll: false } } })"
        ),
        (
            "JSON.stringify({ format: 1, modules: {}, imports: {}, loops: [],\n"
            '  errors: [{ file: "/app/a.js", line: "3", column: 1, message: "" }] })'
        ),
        (
            "JSON.stringify({ format: 1, modules: {}, imports: {}, errors: [],\n"
            '  loops: [{ importer: "/app/a.js", file: "/app/l/a.js" }] })'
        ),
    ],
    ids=[
        "not-json",
        "no-format",
        "format-2",
        "no-errors",
        "no-loops",
        "file-not-a-string",
        "line-not-a-number",
        "loop-without-link",
    ],
)
def test_read_script_modules_rejects_output_of_another_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: str
):
    """Output of another shape, as a script left in .web by another version prints, fails clearly.

    Args:
        tmp_path: pytest tmp_path fixture.
        monkeypatch: pytest monkeypatch fixture.
        output: the JavaScript expression the stand-in prints.
    """
    _require_node()
    web_dir = tmp_path.resolve()
    monkeypatch.setattr(utils, "get_web_dir", lambda: web_dir)
    _write_stand_in(web_dir, output)
    with pytest.raises(ReflexRuntimeError) as error:
        utils._read_script_modules([Path("/app/a.js")])
    assert str(error.value) == (
        f"{web_dir / 'script-modules.js'} printed output that this version of "
        "Reflex does not read, so it is likely left over from another version. "
        f"Delete {web_dir} so that the next run writes it again."
    )


def test_read_script_modules_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """What the real script-modules.js prints is what the compiler reads.

    Args:
        tmp_path: pytest tmp_path fixture.
        monkeypatch: pytest monkeypatch fixture.
    """
    _require_node(packages=True)
    # The script finds the bundler's parser from its directory, as in .web.
    monkeypatch.setattr(
        utils, "get_web_dir", lambda: constants.Templates.Dirs.WEB_TEMPLATE
    )
    fixtures = (FRONTEND_PACKAGE / "tests" / "fixtures" / "script_modules").resolve()
    broken = tmp_path.resolve() / "broken.mjs"
    broken.write_text("export const = 1;\n")
    counter, helpers, format_ = (
        fixtures / "counter.tsx",
        fixtures / "helpers.ts",
        fixtures / "lib" / "format.ts",
    )
    report = utils._read_script_modules([fixtures / "party.ts", counter, broken])
    assert report["modules"][str(counter)] == {
        "files": [str(counter), str(helpers), str(format_)],
        "functions": ["Counter"],
        "values": [],
        "exportsAll": False,
    }
    assert report["imports"][str(counter)] == []
    assert report["errors"] == [
        {"file": str(broken), "line": 1, "column": 14, "message": "Unexpected token"}
    ]
    assert report["loops"] == []


def test_read_script_modules_reports_a_link_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, windows_platform: bool
):
    """The real script reports a file that reaches itself again through a directory link.

    Args:
        tmp_path: pytest tmp_path fixture.
        monkeypatch: pytest monkeypatch fixture.
        windows_platform: Whether symlinks require Windows privileges.
    """
    if windows_platform:
        pytest.skip("Symlinks require additional privileges on Windows")
    _require_node(packages=True)
    monkeypatch.setattr(
        utils, "get_web_dir", lambda: constants.Templates.Dirs.WEB_TEMPLATE
    )
    directory = tmp_path.resolve()
    party, link = directory / "party.js", directory / "loop"
    party.write_text('import "./loop/party.js";\nexport function go() {}\n')
    link.symlink_to(directory)
    assert utils._read_script_modules([party]) == {
        "format": 1,
        "modules": {
            str(party): {
                "files": [str(party)],
                "functions": ["go"],
                "values": [],
                "exportsAll": False,
            }
        },
        "imports": {str(party): []},
        "errors": [],
        "loops": [
            {"importer": str(party), "file": str(link / "party.js"), "link": str(link)}
        ],
    }


def test_link_directory(tmp_path: Path, windows_platform: bool):
    """The link is made once, and what the package holds is what it shows.

    Args:
        tmp_path: pytest tmp_path fixture.
        windows_platform: Whether symlinks require Windows privileges.
    """
    if windows_platform:
        pytest.skip("Symlinks require additional privileges on Windows")
    package = tmp_path / "app"
    (package / "scripts").mkdir(parents=True)
    (package / "scripts" / "old.js").write_text("export const old = 1;\n")
    link = tmp_path / ".web" / "utils" / "script_modules" / "app"
    utils._link_directory(link, package)
    made = link.lstat()
    utils._link_directory(link, package)
    assert link.lstat().st_ino == made.st_ino
    # A file deleted from the package is gone from the bundler's view.
    (package / "scripts" / "old.js").unlink()
    (package / "scripts" / "new.ts").write_text("export const fresh = 1;\n")
    assert sorted(path.name for path in (link / "scripts").iterdir()) == ["new.ts"]


@pytest.mark.parametrize("stale", ["directory", "link", "dangling"])
def test_link_directory_replaces_what_is_there(
    tmp_path: Path, windows_platform: bool, stale: str
):
    """A directory of files, a link elsewhere or a dangling link is replaced.

    Args:
        tmp_path: pytest tmp_path fixture.
        windows_platform: Whether symlinks require Windows privileges.
        stale: what is at the link's path.
    """
    if windows_platform:
        pytest.skip("Symlinks require additional privileges on Windows")
    package = tmp_path / "app"
    package.mkdir()
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "scripts").mkdir(parents=True)
    (elsewhere / "scripts" / "party.js").write_text("")
    link = tmp_path / "script_modules" / "app"
    link.parent.mkdir()
    if stale == "directory":
        shutil.copytree(elsewhere, link)
    else:
        link.symlink_to(elsewhere if stale == "link" else tmp_path / "gone")
    utils._link_directory(link, package)
    assert link.readlink() == package
    # A link elsewhere is removed without what it points to.
    assert (elsewhere / "scripts" / "party.js").is_file()


def test_link_directory_makes_a_junction_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """On Windows, where a symbolic link needs a privilege, the link is a junction.

    Args:
        tmp_path: pytest tmp_path fixture.
        monkeypatch: pytest monkeypatch fixture.
    """
    junctions: list[tuple[str, str]] = []
    winapi = ModuleType("_winapi")
    winapi.CreateJunction = lambda target, link: junctions.append((target, link))  # pyright: ignore[reportAttributeAccessIssue]
    monkeypatch.setitem(sys.modules, "_winapi", winapi)
    monkeypatch.setattr(sys, "platform", "win32")
    link = tmp_path / "script_modules" / "app"
    utils._link_directory(link, tmp_path / "app")
    assert junctions == [(str(tmp_path / "app"), str(link))]
    assert link.parent.is_dir()
