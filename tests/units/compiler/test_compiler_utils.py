from __future__ import annotations

import asyncio
import errno
import importlib
import io
import json
import os
import shutil
import sys
from collections.abc import Generator, Mapping
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any, Literal, TypedDict

import pytest
from reflex_base import constants
from reflex_base.components.memo import create_passthrough_component_memo
from reflex_base.js.modules import _app_modules, _load_module, _ScriptModule
from reflex_base.js.stubs import _TYPESCRIPT_PACKAGE, Signatures, _module_digest
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
        fills, and the paths each of its runs read.
    """
    clean_registration_context._set_config(rx.Config(app_name="app"))
    monkeypatch.setattr(utils, "get_web_dir", lambda: tmp_path / ".web")
    monkeypatch.syspath_prepend(str(tmp_path))
    report: dict = {}
    runs: list[list[Path]] = []

    def read_script_modules(paths: list[Path]) -> dict:
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


@pytest.mark.parametrize("prod", [False, True])
def test_compile_script_modules(
    script_app: tuple[Path, dict, list[list[Path]]],
    monkeypatch: pytest.MonkeyPatch,
    prod: bool,
):
    """Modules are copied with the files they reach and indexed.

    Typescript, which reads their types for their stubs, is installed in every
    mode, so that the app's lockfile is the same in development and production.

    Args:
        script_app: the app package, the stand-in script's output and its runs.
        monkeypatch: pytest monkeypatch fixture.
        prod: whether to compile in production mode.
    """
    if prod:
        monkeypatch.setenv("REFLEX_ENV_MODE", constants.Env.PROD.value)
    package, report, runs = script_app
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
        "loops": [],
    })

    outputs, package_imports, copies, modules = utils.compile_script_modules(
        _app_modules()
    )

    assert runs == [[widget, party, typed]]
    modules_dir = web_dir / "utils" / "script_modules" / "app"
    assert outputs == [
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
    packages = ["canvas-confetti", "dayjs", _TYPESCRIPT_PACKAGE]
    assert package_imports == {
        package: [rx.ImportVar(tag=None, render=False)] for package in packages
    }
    # Each file once, at its path from the directory that holds the package.
    assert copies == [
        (widget, modules_dir / 'my-"widget".js'),
        (helpers, modules_dir / "scripts" / "helpers.js"),
        (party, modules_dir / "scripts" / "party.js"),
        (css, modules_dir / "scripts" / "party.css"),
        (typed, modules_dir / "typed.ts"),
    ]
    # What was read of each module, for its stub.
    assert modules == {
        widget: report["modules"][str(widget)],
        party: report["modules"][str(party)],
        typed: report["modules"][str(typed)],
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
                "and only that directory is copied into the compiled app. Move the "
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
        "loops": [],
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
        "a link back to a directory its imports were already in, so the same "
        "files are imported again one link deeper, without end, and the compiled "
        "app, which copies files and not links, cannot hold them. Import the file "
        f"by a path that does not go through {link}, or replace {link} with a "
        "real directory."
    )


@pytest.mark.parametrize("linked", ["module", "import"])
def test_compile_script_modules_rejects_a_link_to_outside(
    script_app: tuple[Path, dict, list[list[Path]]],
    monkeypatch: pytest.MonkeyPatch,
    windows_platform: bool,
    linked: str,
):
    """A module, or a file it imports, that is a link to a file outside the package is outside it.

    The module is listed by its real path, and a file it imports by the path
    the import names.

    Args:
        script_app: the app package, the stand-in script's output and its runs.
        monkeypatch: pytest monkeypatch fixture.
        windows_platform: Whether symlinks require Windows privileges.
        linked: whether the module or the file it imports is the link.
    """
    if windows_platform:
        pytest.skip("Symlinks require additional privileges on Windows")
    package, report, _ = script_app
    shared = package.parent / "shared" / "vendor.js"
    shared.parent.mkdir()
    shared.write_text("export function shout() {}\n")
    vendor = package / "scripts" / "vendor.js"
    vendor.parent.mkdir(parents=True)
    vendor.symlink_to(shared)
    if linked == "module":
        _import_script_module(monkeypatch, "app.scripts.vendor", vendor, {"shout"})
        module, files = "app.scripts.vendor", [shared]
        outside = f"links to {shared}"
    else:
        party = package / "scripts" / "party.js"
        _import_script_module(monkeypatch, "app.scripts.party", party, {"shout"})
        module, files = "app.scripts.party", [party, vendor]
        outside = f"imports {vendor}, a link to {shared}"
    report.update({
        "modules": {str(files[0]): _script_exports(files, ["shout"])},
        "imports": {},
        "errors": [],
        "loops": [],
    })
    with pytest.raises(ReflexRuntimeError) as error:
        utils.compile_script_modules(_app_modules())
    assert str(error.value) == (
        f"The JavaScript module {module} {outside}, which is outside "
        f"{package}, the directory of the app's package, and only that "
        "directory is copied into the compiled app. Move the file into it, or "
        "publish it as an npm package and import it by name."
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
        "loops": [],
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
        [],
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
            dependencies, the scripts' vite and typescript, which
            ``npm --prefix packages/reflex-frontend ci`` installs.
    """
    node_modules = FRONTEND_PACKAGE / "node_modules"
    if shutil.which("node") and (
        not packages
        or ((node_modules / "vite").is_dir() and (node_modules / "typescript").is_dir())
    ):
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


@pytest.fixture
def stub_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[Path, Any]]:
    """An app with a JavaScript module, whose `.web` reads types with a fake script.

    The fake signatures script is Python code under the JavaScript script's
    name, run by this interpreter in place of Node.js, so the real subprocess
    call runs on every platform.

    Args:
        tmp_path: pytest tmp_path fixture.
        monkeypatch: pytest monkeypatch fixture.

    Returns:
        The module, and what was read of it, by its file.
    """
    web_dir = tmp_path / ".web"
    web_dir.mkdir()
    monkeypatch.setattr(utils, "get_web_dir", lambda: web_dir)
    monkeypatch.setattr(utils.path_ops, "get_node_path", lambda: Path(sys.executable))
    party = tmp_path / "app" / "party.js"
    party.parent.mkdir()
    party.write_text("/** @param {number} n */\nexport function go(n) {}\n")
    return party, {party: _script_exports([party], ["go"])}


def _fake_signatures(body: str):
    """Make the fake signatures script run some Python, logging each run.

    Args:
        body: The Python code, which can use ``sys``.
    """
    (utils.get_web_dir() / "script-signatures.js").write_text(
        "import sys\n"
        "with open(sys.argv[0] + '.log', 'a') as log:\n"
        "    log.write(' '.join(sys.argv[1:]) + '\\n')\n" + body
    )


def _write_stubs(modules: Mapping[Path, Any]) -> list[tuple[str, str]]:
    """Write the stubs of modules, recording the files written.

    Args:
        modules: What was read of each module, by its file.

    Returns:
        The (path, content) of each file written, of which an unchanged one is
        left alone.
    """
    written: list[tuple[str, str]] = []
    write_file = utils.write_file

    def record(path: Path, code: str, **kwargs) -> None:
        written.append((str(path), code))
        write_file(path, code, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(utils, "write_file", record)
        utils.write_script_stubs(modules)
    return written


def test_write_script_stubs(stub_app: tuple[Path, dict[Path, Any]]):
    """A stub is typed from the module's signatures, and kept while nothing changed.

    What it is made from is the module's files and the files its types were
    read from, among them the package.json of a package they read, which the
    record keeps for the next compile.

    Args:
        stub_app: the module, and what was read of it.
    """
    party, modules = stub_app
    web_dir = utils.get_web_dir()
    # A declaration file only types read, which the bundler never loads.
    shapes = party.with_name("shapes.d.ts")
    shapes.write_text('export type Shape = "circle";\n')
    package = web_dir / "node_modules" / "a" / "package.json"
    package.parent.mkdir(parents=True)
    package.write_text('{"name": "a", "version": "1.0.0"}')
    type_files = [str(party), str(shapes), str(package)]
    parameter = {"name": "n", "type": "float", "optional": False, "rest": False}
    _fake_signatures(
        "print({!r})\n".format(
            json.dumps({
                "format": 1,
                "modules": {str(party): {"go": [{"parameters": [parameter]}]}},
                "files": {str(party): type_files},
            })
        )
    )
    record = (
        str(web_dir / "script_stubs.json"),
        json.dumps({str(party): type_files}),
    )

    def stub() -> tuple[str, str]:
        digest = _module_digest(party, type_files)
        return str(party.with_suffix(".pyi")), (
            f"# Generated by Reflex from party.js ({digest}); rewritten when it changes.\n"
            "from builtins import float as _float\n"
            "\n"
            "from reflex_base.event import EventSpec as _EventSpec\n"
            "from reflex_base.vars.base import Var as _Var\n"
            "\n"
            "def go(n: _float | _Var[_float], /) -> _EventSpec: ...\n"
        )

    assert _write_stubs(modules) == [stub(), record]
    # Unchanged sources keep their stub without reading the types again.
    assert _write_stubs(modules) == [record]
    # A file the types were read from changed, or is gone: they are read again.
    shapes.write_text('export type Shape = "square";\n')
    assert _write_stubs(modules) == [stub(), record]
    shapes.unlink()
    assert _write_stubs(modules) == [stub(), record]
    assert _write_stubs(modules) == [record]
    # An upgrade of a package the types were read from can change them too.
    package.write_text('{"name": "a", "version": "1.1.0"}')
    assert _write_stubs(modules) == [stub(), record]
    assert _write_stubs(modules) == [record]
    assert (web_dir / "script-signatures.js.log").read_text() == f"{party}\n" * 4


@pytest.mark.parametrize(
    ("killed_at", "new_type_file"),
    [
        # Writing the stub, after a change to the module.
        ("# Generated by Reflex", False),
        # Writing the record, after the module reads types from a new file.
        ("{", True),
    ],
    ids=["stub", "record"],
)
def test_write_script_stubs_after_a_compile_killed_mid_write(
    stub_app: tuple[Path, dict[Path, Any]],
    monkeypatch: pytest.MonkeyPatch,
    killed_at: str,
    new_type_file: bool,
):
    """A compile killed while it writes a stub or the record leaves neither half written.

    A half-written stub whose header is whole would be kept as current, and a
    half-written record would stop every later compile. The next compile writes
    both whole.

    Args:
        stub_app: the module, and what was read of it.
        monkeypatch: pytest monkeypatch fixture.
        killed_at: the start of the content being written when the compile is
            killed.
        new_type_file: whether the change before that compile adds a file the
            module's types are read from.
    """
    party, modules = stub_app
    web_dir = utils.get_web_dir()
    shapes = party.with_name("shapes.d.ts")
    parameter = {"name": "n", "type": "float", "optional": False, "rest": False}
    _fake_signatures(
        "import os\n"
        + _print_signatures(
            repr({"go": [{"parameters": [parameter]}]}),
            f"[f for f in {[str(party), str(shapes)]!r} if os.path.exists(f)]",
        )
    )
    io_open = io.open

    def open_killed(file, mode="r", *args, **kwargs):
        handle: Any = io_open(file, mode, *args, **kwargs)
        write = handle.write

        def killed(data: str) -> int:
            if not data.startswith(killed_at):
                return write(data)
            write(data[: len(data) // 2])
            handle.flush()
            raise KeyboardInterrupt

        handle.write = killed
        return handle

    utils.write_script_stubs(modules)
    party.write_text(party.read_text() + "// changed\n")
    if new_type_file:
        shapes.write_text("export type Shape = string;\n")
    type_files = [str(party), *([str(shapes)] if new_type_file else [])]
    with monkeypatch.context() as patch, pytest.raises(KeyboardInterrupt):
        patch.setattr(io, "open", open_killed)
        utils.write_script_stubs(modules)
    utils.write_script_stubs(modules)

    digest = _module_digest(party, [str(party), *type_files])
    assert party.with_suffix(".pyi").read_text() == (
        f"# Generated by Reflex from party.js ({digest}); rewritten when it changes.\n"
        "from builtins import float as _float\n"
        "\n"
        "from reflex_base.event import EventSpec as _EventSpec\n"
        "from reflex_base.vars.base import Var as _Var\n"
        "\n"
        "def go(n: _float | _Var[_float], /) -> _EventSpec: ...\n"
    )
    assert (web_dir / "script_stubs.json").read_text() == json.dumps({
        str(party): type_files
    })
    # No temporary file is left beside them.
    assert sorted(path.name for path in party.parent.iterdir()) == [
        "party.js",
        "party.pyi",
        *(["shapes.d.ts"] if new_type_file else []),
    ]
    assert sorted(path.name for path in web_dir.iterdir()) == [
        "script-signatures.js",
        "script-signatures.js.log",
        "script_stubs.json",
    ]


@pytest.mark.parametrize(
    "record",
    ['{"/app/party.js": [', '["/app/party.js"]', '{"<party>": "<party>"}'],
    ids=["cut-short", "list", "files-not-a-list"],
)
def test_write_script_stubs_rewrites_a_record_of_another_shape(
    stub_app: tuple[Path, dict[Path, Any]], record: str
):
    """A record that this version does not read, as another version can leave, reads as empty.

    Args:
        stub_app: the module, and what was read of it.
        record: the record, with ``<party>`` for the module's file.
    """
    party, modules = stub_app
    web_dir = utils.get_web_dir()
    (web_dir / "script_stubs.json").write_text(
        record.replace("<party>", json.dumps(str(party))[1:-1])
    )
    _fake_signatures(_print_signatures("{}", repr([str(party)])))
    digest = _module_digest(party, [str(party)])
    assert _write_stubs(modules) == [
        (
            str(party.with_suffix(".pyi")),
            (
                f"# Generated by Reflex from party.js ({digest}); rewritten when "
                "it changes.\n"
                "from typing import Any as _Any\n"
                "\n"
                "from reflex_base.event import EventSpec as _EventSpec\n"
                "\n"
                "def go(*args: _Any) -> _EventSpec: ...\n"
            ),
        ),
        (
            str(web_dir / "script_stubs.json"),
            json.dumps({str(party): [str(party)]}),
        ),
    ]


def test_write_script_stubs_warns_when_a_stub_cannot_be_written(
    stub_app: tuple[Path, dict[Path, Any]], monkeypatch: pytest.MonkeyPatch
):
    """A stub that cannot be written or removed is warned about, and the compile goes on.

    The module's directory is made read-only by refusing writes to it, which a
    chmod cannot do for root, and does not do for directories on Windows.

    Args:
        stub_app: the module, and what was read of it.
        monkeypatch: pytest monkeypatch fixture.
    """
    party, modules = stub_app
    stub = party.with_suffix(".pyi")
    _fake_signatures(_print_signatures("{}", repr([str(party)])))
    warnings: list[str] = []
    monkeypatch.setattr(utils.console, "warn", warnings.append)
    write_file, unlink = utils.write_file, Path.unlink

    def refuse(path: Path) -> None:
        if path.parent == party.parent:
            raise PermissionError(errno.EACCES, "Permission denied", str(path))

    def read_only_write(path: Path, code: str, **kwargs) -> None:
        refuse(path)
        write_file(path, code, **kwargs)

    def read_only_unlink(self: Path, missing_ok: bool = False) -> None:
        refuse(self)
        unlink(self, missing_ok=missing_ok)

    with monkeypatch.context() as patch:
        patch.setattr(utils, "write_file", read_only_write)
        utils.write_script_stubs(modules)
    assert not stub.exists()
    utils.write_script_stubs(modules)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", read_only_unlink)
        utils.write_script_stubs({})
    assert stub.exists()
    assert warnings == [
        (
            f"Reflex could not write the type stub {stub}: Permission denied. "
            "Type checkers do not see the functions of party.js until it is "
            f"written; the app still runs. Make {party.parent} writable, and the "
            "next compile writes it."
        ),
        (
            f"Reflex could not remove the type stub {stub}, which it wrote for a "
            "JavaScript module the app no longer imports: Permission denied. "
            "Delete the file."
        ),
    ]


def test_write_script_stubs_keeps_a_stub_written_by_hand(
    stub_app: tuple[Path, dict[Path, Any]],
):
    """A stub without Reflex's header, as one written by hand, is never rewritten.

    Args:
        stub_app: the module, and what was read of it.
    """
    party, modules = stub_app
    stub = party.with_suffix(".pyi")
    stub.write_text("def go(n: int) -> None: ...\n")
    _fake_signatures(_print_signatures("{}", repr([str(party)])))
    utils.write_script_stubs(modules)
    assert stub.read_text() == "def go(n: int) -> None: ...\n"
    # Nor are its module's types read.
    assert not (utils.get_web_dir() / "script-signatures.js.log").exists()


def test_write_script_stubs_keeps_a_stub_that_is_not_utf8(
    stub_app: tuple[Path, dict[Path, Any]], monkeypatch: pytest.MonkeyPatch
):
    """A stub in another encoding has no header of Reflex's, so it is kept as is.

    Args:
        stub_app: the module, and what was read of it.
        monkeypatch: pytest monkeypatch fixture.
    """
    party, modules = stub_app
    stub = party.with_suffix(".pyi")
    code = "# -*- coding: latin-1 -*-\n# café\ndef go(n: int) -> None: ...\n"
    stub.write_bytes(code.encode("latin-1"))
    _fake_signatures(_print_signatures("{}", repr([str(party)])))
    warnings: list[str] = []
    monkeypatch.setattr(utils.console, "warn", warnings.append)
    utils.write_script_stubs(modules)
    utils.write_script_stubs({})
    assert stub.read_bytes() == code.encode("latin-1")
    assert warnings == []


def test_write_script_stubs_keeps_a_stub_it_cannot_read(
    stub_app: tuple[Path, dict[Path, Any]], monkeypatch: pytest.MonkeyPatch
):
    """A stub that cannot be read is warned about and kept, and the compile goes on.

    Args:
        stub_app: the module, and what was read of it.
        monkeypatch: pytest monkeypatch fixture.
    """
    party, modules = stub_app
    # A directory, which no platform opens as a file, even for root.
    stub = party.with_suffix(".pyi")
    stub.mkdir()
    with pytest.raises(OSError) as refused:
        stub.open("rb")
    _fake_signatures(_print_signatures("{}", repr([str(party)])))
    warnings: list[str] = []
    monkeypatch.setattr(utils.console, "warn", warnings.append)
    utils.write_script_stubs(modules)
    assert stub.is_dir()
    assert not (utils.get_web_dir() / "script-signatures.js.log").exists()
    assert warnings == [
        (
            f"Reflex could not read the type stub {stub}: "
            f"{refused.value.strerror}. It leaves the file as it is, as it does "
            "a stub written by hand. Make the file readable, or delete it so that "
            "the next compile writes it."
        )
    ]


def test_write_script_stubs_of_a_linked_module(
    stub_app: tuple[Path, dict[Path, Any]],
):
    """A module that links elsewhere gets its stub beside the link, typed from its file.

    Python imports it by the link, where type checkers look for the stub; the
    types are read, and the digest taken, at the real path the module's files
    are listed by.

    Args:
        stub_app: the module, and what was read of it.
    """
    party, _ = stub_app
    shared = party.parent.parent / "shared" / "party.js"
    shared.parent.mkdir()
    shared.write_text(party.read_text())
    link = party.with_name("linked.js")
    link.symlink_to(shared)
    parameter = {"name": "n", "type": "float", "optional": False, "rest": False}
    _fake_signatures(
        _print_signatures(repr({"go": [{"parameters": [parameter]}]}), "[sys.argv[1]]")
    )
    web_dir = utils.get_web_dir()
    digest = _module_digest(shared, [str(shared), str(shared)])
    assert _write_stubs({link: _script_exports([shared], ["go"])}) == [
        (
            str(party.with_name("linked.pyi")),
            (
                f"# Generated by Reflex from linked.js ({digest}); rewritten when "
                "it changes.\n"
                "from builtins import float as _float\n"
                "\n"
                "from reflex_base.event import EventSpec as _EventSpec\n"
                "from reflex_base.vars.base import Var as _Var\n"
                "\n"
                "def go(n: _float | _Var[_float], /) -> _EventSpec: ...\n"
            ),
        ),
        (str(web_dir / "script_stubs.json"), json.dumps({str(link): [str(shared)]})),
    ]
    assert (web_dir / "script-signatures.js.log").read_text() == f"{shared}\n"


def test_write_script_stubs_removes_stubs_of_modules_no_longer_imported(
    stub_app: tuple[Path, dict[Path, Any]],
):
    """Only stubs Reflex wrote for a module the app stopped importing are removed.

    Args:
        stub_app: the module, and what was read of it.
    """
    party, modules = stub_app
    web_dir = utils.get_web_dir()
    _fake_signatures(
        "print({!r})\n".format(
            json.dumps({
                "format": 1,
                "modules": {str(party): {}},
                "files": {str(party): []},
            })
        )
    )
    # No module and no stub written before: nothing to record.
    assert _write_stubs({}) == []
    handwritten = party.with_name("handwritten.pyi")
    handwritten.write_text("def go() -> None: ...\n")
    (web_dir / "script_stubs.json").write_text(
        json.dumps({str(handwritten.with_suffix(".js")): []})
    )
    _write_stubs(modules)
    stub = party.with_suffix(".pyi")
    assert stub.read_text() == (
        "# Generated by Reflex from party.js "
        f"({_module_digest(party, [str(party)])}); "
        "rewritten when it changes.\n"
        "from typing import Any as _Any\n"
        "\n"
        "from reflex_base.event import EventSpec as _EventSpec\n"
        "\n"
        "def go(*args: _Any) -> _EventSpec: ...\n"
    )

    assert _write_stubs({}) == [(str(web_dir / "script_stubs.json"), "{}")]
    assert (stub.exists(), handwritten.read_text()) == (
        False,
        "def go() -> None: ...\n",
    )


# Why the types of a module could not be read, and the fix, after a stand-in
# for script-signatures.js printed output of another shape.
_UNREADABLE_SIGNATURES = (
    "{web_dir}/script-signatures.js printed output that this version of Reflex "
    "does not read, so it is likely left over from another version. Delete "
    "{web_dir} so that the next run writes it again."
)


def _print_signatures(modules: str, files: str = "[]", format_: str = "1") -> str:
    """Make the fake signatures script print output for the module ``party``.

    Args:
        modules: The Python expression of the signatures of its exports.
        files: The Python expression of the files its types were read from.
        format_: The Python expression of the output's format.

    Returns:
        The script's code, which prints the output.
    """
    return (
        "import json\n"
        f"print(json.dumps({{'format': {format_}, 'files': {{sys.argv[1]: {files}}}, "
        f"'modules': {{sys.argv[1]: {modules}}}}}))\n"
    )


@pytest.mark.parametrize(
    ("body", "timeout", "reason"),
    [
        (
            (
                "sys.stderr.write(\"Error: Cannot find module 'typescript'\\n\")\n"
                "sys.exit(1)\n"
            ),
            utils._SIGNATURES_TIMEOUT,
            (
                "script-signatures.js failed. If this repeats, delete "
                "{web_dir}/node_modules so that the next run reinstalls typescript, "
                "or report the error at https://github.com/reflex-dev/reflex/issues:\n"
                "Error: Cannot find module 'typescript'"
            ),
        ),
        (
            "import time\ntime.sleep(30)\n",
            0.5,
            (
                "script-signatures.js failed. If this repeats, delete "
                "{web_dir}/node_modules so that the next run reinstalls typescript, "
                "or report the error at https://github.com/reflex-dev/reflex/issues:\n"
                "Command '{command}' timed out after 0.5 seconds"
            ),
        ),
        ("print('Debugger attached.')\n", 1, _UNREADABLE_SIGNATURES),
        # The output of another version of the script.
        (
            'print(\'{"modules": {}, "files": []}\')\n',
            1,
            _UNREADABLE_SIGNATURES,
        ),
        (_print_signatures("{}", format_="2"), 1, _UNREADABLE_SIGNATURES),
        # The right version, of another shape: files not strings, a parameter
        # without `rest`, a type of an unknown kind deep in another.
        (_print_signatures("{}", files="[1]"), 1, _UNREADABLE_SIGNATURES),
        (
            _print_signatures(
                "{'go': [{'parameters': [{'name': 'n', 'type': 'float', "
                "'optional': False}]}]}"
            ),
            1,
            _UNREADABLE_SIGNATURES,
        ),
        (
            _print_signatures(
                "{'go': [{'parameters': [{'name': 'n', 'optional': False, "
                "'rest': False, 'type': {'kind': 'list', 'item': {'kind': "
                "'union', 'members': ['str', {'kind': 'set', 'item': 'str'}]}}}]}]}"
            ),
            1,
            _UNREADABLE_SIGNATURES,
        ),
    ],
    ids=[
        "fails",
        "times-out",
        "not-json",
        "no-format",
        "format-2",
        "files-not-strings",
        "no-rest",
        "nested-unknown-kind",
    ],
)
def test_write_script_stubs_warns_when_the_types_cannot_be_read(
    stub_app: tuple[Path, dict[Path, Any]],
    monkeypatch: pytest.MonkeyPatch,
    body: str,
    timeout: float,
    reason: str,
):
    """The stub accepts any arguments, the warning says why, and the next compile retries.

    Args:
        stub_app: the module, and what was read of it.
        monkeypatch: pytest monkeypatch fixture.
        body: the fake signatures script's code.
        timeout: how long the script may run.
        reason: why the warning says the types could not be read, with
            ``{web_dir}`` for the web directory and ``{command}`` for the
            command that ran.
    """
    party, modules = stub_app
    web_dir = utils.get_web_dir()
    _fake_signatures(body)
    monkeypatch.setattr(utils, "_SIGNATURES_TIMEOUT", timeout)
    warnings: list[str] = []
    monkeypatch.setattr(utils.console, "warn", warnings.append)
    untyped = (
        str(party.with_suffix(".pyi")),
        (
            "# Generated by Reflex from party.js (untyped); rewritten when it changes.\n"
            "from typing import Any as _Any\n"
            "\n"
            "from reflex_base.event import EventSpec as _EventSpec\n"
            "\n"
            "def go(*args: _Any) -> _EventSpec: ...\n"
        ),
    )
    assert _write_stubs(modules)[:-1] == [untyped]
    assert _write_stubs(modules)[:-1] == [untyped]
    command = [sys.executable, "script-signatures.js", str(party)]
    warning = (
        "Reflex could not read the argument types of the JavaScript modules "
        f"{party}, so their type stubs accept any arguments; the app still runs. "
        + reason.format(web_dir=web_dir, command=command)
    )
    assert warnings == [warning, warning]


def test_parse_json_reads_the_signatures_the_real_script_prints():
    """The output script-signatures.js prints for its fixtures has the shape read.

    Its vitest checks that the script prints the fixture.
    """
    output = (
        FRONTEND_PACKAGE / "tests" / "fixtures" / "signatures" / "signatures.json"
    ).read_text()
    assert utils._parse_json(output, Signatures) == json.loads(output)


def test_write_script_stubs_with_the_real_scripts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """A TypeScript and a JSDoc module are read by the scripts Reflex runs, through to their stubs.

    A declaration file only their types read is not copied into the app, and
    a change to it rewrites the stubs; a change to one module rewrites only its
    own.

    Args:
        tmp_path: pytest tmp_path fixture.
        monkeypatch: pytest monkeypatch fixture.
    """
    _require_node(packages=True)
    web_dir = tmp_path / ".web"
    web_dir.mkdir()
    for script in ("script-modules.js", "script-signatures.js"):
        shutil.copy(constants.Templates.Dirs.WEB_TEMPLATE / script, web_dir)
    (web_dir / "node_modules").symlink_to(
        FRONTEND_PACKAGE / "node_modules", target_is_directory=True
    )
    (web_dir / "package.json").write_text("{}")
    monkeypatch.setattr(utils, "get_web_dir", lambda: web_dir)
    package = tmp_path.resolve() / "app"
    package.mkdir()
    shapes = package / "shapes.d.ts"
    shapes.write_text('export type Shape = "circle" | "square";\n')
    draw = package / "draw.ts"
    draw.write_text(
        'import type { Shape } from "./shapes";\n'
        "export function draw(shape: Shape, size?: number): void {}\n"
    )
    party = package / "party.js"
    party.write_text(
        '/** @param {import("./shapes").Shape} shape @param {string} id */\n'
        "export function place(shape, id) {}\n"
    )
    _, _, copies, modules = utils.compile_script_modules({
        "app.draw": _ScriptModule(draw, {"draw"}),
        "app.party": _ScriptModule(party, {"place"}),
    })

    modules_dir = web_dir / "utils" / "script_modules" / "app"
    assert copies == [
        (draw, modules_dir / "draw.ts"),
        (party, modules_dir / "party.js"),
    ]
    # Each module's own: neither lists the other.
    type_files = {
        draw: [str(draw), str(shapes)],
        party: [str(party), str(shapes)],
    }
    record = (
        str(web_dir / "script_stubs.json"),
        json.dumps({str(path): files for path, files in type_files.items()}),
    )

    def stubs(shape: str) -> list[tuple[str, str]]:
        literal = f"_Literal[{shape}]"
        header = "# Generated by Reflex from {} ({}); rewritten when it changes.\n"
        imports = (
            "from builtins import {}\n"
            "from typing import {}Literal as _Literal\n"
            "\n"
            "from reflex_base.event import {}EventSpec as _EventSpec\n"
            "from reflex_base.vars.base import Var as _Var\n"
            "\n"
        )
        return [
            (
                str(path.with_suffix(".pyi")),
                header.format(
                    path.name,
                    _module_digest(path, [str(path), *type_files[path]]),
                )
                + body,
            )
            for path, body in [
                (
                    draw,
                    imports.format("float as _float", "", "")
                    + f"def draw(shape: {literal} | _Var[{literal}], "
                    "size: _float | _Var[_float] = ..., /) -> _EventSpec: ...\n",
                ),
                (
                    party,
                    imports.format(
                        "str as _str, tuple as _tuple",
                        "Any as _Any, ",
                        "EventCallback as _EventCallback, ",
                    )
                    + f"def place(shape: {literal} | _Var[{literal}], id: _str | "
                    "_Var[_str] | _EventCallback[*_tuple[_Any, ...]], /) -> "
                    "_EventSpec: ...\n",
                ),
            ]
        ]

    assert _write_stubs(modules) == [*stubs('"circle", "square"'), record]
    assert _write_stubs(modules) == [record]
    shapes.write_text('export type Shape = "circle" | "star";\n')
    assert _write_stubs(modules) == [*stubs('"circle", "star"'), record]
    # A change to one module leaves the other's stub as it is.
    draw.write_text(draw.read_text() + "// edited\n")
    assert _write_stubs(modules) == [stubs('"circle", "star"')[0], record]


def test_write_script_stubs_follows_only_what_the_types_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """A stub is rewritten when a package its types are read from changes, not Reflex's files or other packages.

    The module imports ``$/utils/reflex``, which reaches ``env.json``,
    ``utils/scripts.js`` and through it the ``.web`` copies of every module:
    Reflex's own files, which a new port or another module changes. Neither
    they nor the app's other packages change the stub's types.

    Args:
        tmp_path: pytest tmp_path fixture.
        monkeypatch: pytest monkeypatch fixture.
    """
    _require_node(packages=True)
    web_dir = tmp_path.resolve() / ".web"
    (web_dir / "utils").mkdir(parents=True)
    shutil.copy(constants.Templates.Dirs.WEB_TEMPLATE / "script-signatures.js", web_dir)
    node_modules = web_dir / "node_modules"
    node_modules.mkdir()
    (node_modules / "typescript").symlink_to(
        FRONTEND_PACKAGE / "node_modules" / "typescript", target_is_directory=True
    )
    package = node_modules / "shapes"
    package.mkdir()
    (package / "package.json").write_text('{"name": "shapes", "version": "1.0.0"}')
    (package / "index.d.ts").write_text('export type Shape = "circle";\n')
    (web_dir / "package.json").write_text('{"dependencies": {"shapes": "1.0.0"}}')
    (web_dir / "env.json").write_text('{"EVENT": "http://localhost:8000/_event"}')
    (web_dir / "utils" / "scripts.js").write_text("export default {};\n")
    (web_dir / "utils" / "reflex.js").write_text(
        'import env from "$/env.json";\n'
        'import scripts from "$/utils/scripts";\n'
        "export const call = (name) => [env, scripts, name];\n"
    )
    monkeypatch.setattr(utils, "get_web_dir", lambda: web_dir)
    party = tmp_path.resolve() / "app" / "party.ts"
    party.parent.mkdir()
    party.write_text(
        'import { call } from "$/utils/reflex";\n'
        'import type { Shape } from "shapes";\n'
        "export function draw(shape: Shape) { call(shape); }\n"
    )
    modules = {party: _script_exports([party], ["draw"])}

    def write() -> list[str]:
        """Write the stub.

        Returns:
            The names of the files written.
        """
        return [Path(path).name for path, _ in _write_stubs(modules)]

    assert write() == ["party.pyi", "script_stubs.json"]
    # A new port, another module, another package of the app.
    (web_dir / "env.json").write_text('{"EVENT": "http://localhost:8001/_event"}')
    other = web_dir / "utils" / "script_modules" / "app" / "other.js"
    other.parent.mkdir(parents=True)
    other.write_text("export function go() {}\n")
    (web_dir / "utils" / "scripts.js").write_text(
        'export default {"app.other": () => import("$/utils/script_modules/app/other.js")};\n'
    )
    (web_dir / "package.json").write_text(
        '{"dependencies": {"dayjs": "1.11.0", "shapes": "1.0.0"}}'
    )
    (web_dir / "bun.lock").write_text('{"packages": {"dayjs": ["dayjs@1.11.0"]}}')
    assert write() == ["script_stubs.json"]
    # An upgrade of the package the types are read from, within the range
    # package.json allows.
    (package / "package.json").write_text('{"name": "shapes", "version": "1.1.0"}')
    (package / "index.d.ts").write_text('export type Shape = "circle" | "star";\n')
    assert write() == ["party.pyi", "script_stubs.json"]
    literal = '_Literal["circle", "star"]'
    assert (
        party
        .with_suffix(".pyi")
        .read_text()
        .endswith(
            f"def draw(shape: {literal} | _Var[{literal}], /) -> _EventSpec: ...\n"
        )
    )
    assert json.loads((web_dir / "script_stubs.json").read_text()) == {
        str(party): [str(party), str(package / "package.json")]
    }


def test_copy_files_skips_up_to_date_targets(tmp_path: Path):
    """A target with the same bytes is left alone; others are written.

    Args:
        tmp_path: pytest tmp_path fixture.
    """
    source = tmp_path / "logo.png"
    source.write_bytes(b"\x89PNG\xff")
    target = tmp_path / "out" / "nested" / "logo.png"
    utils.copy_files([(source, target)])
    assert target.read_bytes() == b"\x89PNG\xff"
    modified = target.stat().st_mtime_ns
    utils.copy_files([(source, target)])
    assert target.stat().st_mtime_ns == modified
    source.write_bytes(b"\x89PNG\x00")
    utils.copy_files([(source, target)])
    assert target.read_bytes() == b"\x89PNG\x00"
