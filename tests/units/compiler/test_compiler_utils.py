from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

import pytest
from reflex_base import constants
from reflex_base.components.memo import create_passthrough_component_memo
from reflex_base.js.modules import _ScriptModule
from reflex_base.js.stubs import _TYPESCRIPT_PACKAGE, _module_digest
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
) -> tuple[Path, dict, list[list[Path]]]:
    """An app package that imports JavaScript modules, read by a stand-in script.

    Args:
        tmp_path: pytest tmp_path fixture.
        monkeypatch: pytest monkeypatch fixture.
        clean_registration_context: a fresh registry of imported modules.

    Returns:
        The package's directory, the output of the stand-in, which the test
        fills, and the paths each of its runs read.
    """
    monkeypatch.setattr(utils, "get_web_dir", lambda: tmp_path / ".web")
    report: dict = {}
    runs: list[list[Path]] = []

    def read_script_modules(paths: list[Path]) -> dict:
        runs.append(paths)
        return report

    monkeypatch.setattr(utils, "_read_script_modules", read_script_modules)
    return tmp_path.resolve() / "app", report, runs


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
    clean_registration_context: RegistrationContext,
    monkeypatch: pytest.MonkeyPatch,
    prod: bool,
):
    """Modules are copied with the files they reach and indexed.

    Typescript, which reads their types for their stubs, is installed only in
    development.

    Args:
        script_app: the app package, the stand-in script's output and its runs.
        clean_registration_context: a fresh registry of imported modules.
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
    clean_registration_context._script_modules.update({
        "app.typed": _ScriptModule(typed, {"typed", "fromStar"}),
        "app.scripts.party": _ScriptModule(party, {"celebrate"}),
        'app.my-"widget"': _ScriptModule(widget, {"show"}),
    })
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

    outputs, package_imports, copies, modules = utils.compile_script_modules()

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
    packages = ["canvas-confetti", "dayjs", *([] if prod else [_TYPESCRIPT_PACKAGE])]
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
                    "file": "{project}/app/scripts/helpers.js",
                    "line": 3,
                    "column": 7,
                    "message": "Unexpected token",
                }
            ],
            (
                "Syntax error at {project}/app/scripts/helpers.js:3:7: Unexpected "
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
                "`nope` is used from app.scripts.party, but app/scripts/party.js "
                "exports no function named nope (its functions: celebrate, launch). "
                "Export it from app/scripts/party.js, as in `export function nope() "
                "{ ... }`, or correct the name in Python."
            ),
        ),
        (
            {"limit"},
            ["app/scripts/party.js"],
            [],
            [],
            (
                "`limit` is used from app.scripts.party as a function, but "
                "app/scripts/party.js exports limit as a value, and Python can only "
                "call functions. Export a function instead, as in `export function "
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
                "The JavaScript module app.scripts.party imports {project}/.env, "
                "which is outside {project}/app, the directory of the app's package, "
                "and only that directory is copied into the compiled app. Move the "
                "file into it, or publish it as an npm package and import it by name."
            ),
        ),
    ],
)
def test_compile_script_modules_errors(
    script_app: tuple[Path, dict, list[list[Path]]],
    clean_registration_context: RegistrationContext,
    names: set[str],
    files: list[str],
    functions: list[str],
    errors: list[dict],
    message: str,
):
    """A syntax error, a name not exported as a function, a file outside the package.

    Args:
        script_app: the app package, the stand-in script's output and its runs.
        clean_registration_context: a fresh registry of imported modules.
        names: the names Python uses.
        files: the files the module reaches, from the project's directory.
        functions: the module's functions.
        errors: the syntax errors.
        message: the expected error, with ``{project}`` for the project's
            directory.
    """
    package, report, _ = script_app
    project = str(package.parent)
    party = package / "scripts" / "party.js"
    clean_registration_context._script_modules["app.scripts.party"] = _ScriptModule(
        party, names
    )
    report.update({
        "modules": {
            str(party): _script_exports(
                [package.parent / file for file in files], functions, ["limit"]
            )
        },
        "imports": {},
        "errors": [
            {**error, "file": error["file"].replace("{project}", project)}
            for error in errors
        ],
    })
    with pytest.raises(ReflexRuntimeError) as error:
        utils.compile_script_modules()
    assert str(error.value) == message.replace("{project}", project)


def test_compile_script_modules_without_modules(
    script_app: tuple[Path, dict, list[list[Path]]],
):
    """An app that imports no JavaScript module gets an empty index, and runs no script.

    Args:
        script_app: the app package, the stand-in script's output and its runs.
    """
    _, _, runs = script_app
    assert utils.compile_script_modules() == (
        [(str(utils.get_web_dir() / "utils" / "scripts.js"), "export default {};\n")],
        {},
        [],
        {},
    )
    assert runs == []


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_read_script_modules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The script runs in .web on the modules, and its failure says how to recover.

    Args:
        tmp_path: pytest tmp_path fixture.
        monkeypatch: pytest monkeypatch fixture.
    """
    web_dir = tmp_path.resolve()
    monkeypatch.setattr(utils, "get_web_dir", lambda: web_dir)
    script = web_dir / "script-modules.js"
    script.write_text(
        "process.stdout.write(JSON.stringify({\n"
        "  cwd: process.cwd(), modules: process.argv.slice(2) }));\n"
    )
    assert utils._read_script_modules([Path("/app/a.js"), Path("/app/b.ts")]) == {
        "cwd": str(web_dir),
        "modules": ["/app/a.js", "/app/b.ts"],
    }
    script.write_text('process.stderr.write("Error: boom\\n"); process.exit(3);\n')
    with pytest.raises(ReflexRuntimeError) as error:
        utils._read_script_modules([Path("/app/a.js")])
    assert str(error.value) == (
        "Reflex could not read the JavaScript modules the app imports from "
        "Python: script-modules.js failed. If this repeats, delete "
        f"{web_dir / 'node_modules'} so that the next run reinstalls the "
        "frontend packages, or report the error at "
        "https://github.com/reflex-dev/reflex/issues:\nError: boom"
    )


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
    (web_dir / "package.json").write_text('{"dependencies": {"a": "1"}}')
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


def _compile_stubs(modules: Mapping[Path, Any]) -> list[tuple[str, str]]:
    """Compile the stubs of modules, writing the outputs to disk.

    Args:
        modules: What was read of each module, by its file.

    Returns:
        The outputs of ``compile_script_stubs``.
    """
    outputs = utils.compile_script_stubs(modules)
    for path, code in outputs:
        Path(path).write_text(code)
    return outputs


def test_compile_script_stubs(stub_app: tuple[Path, dict[Path, Any]]):
    """A stub is typed from the module's signatures, and kept while nothing changed.

    What it is made from is the module's files, the files its types were read
    from, which the record keeps for the next compile, and the app's packages.

    Args:
        stub_app: the module, and what was read of it.
    """
    party, modules = stub_app
    web_dir = utils.get_web_dir()
    # A declaration file only types read, which the bundler never loads.
    shapes = party.with_name("shapes.d.ts")
    shapes.write_text('export type Shape = "circle";\n')
    parameter = {"name": "n", "type": "float", "optional": False, "rest": False}
    _fake_signatures(
        "print({!r})\n".format(
            json.dumps({
                "modules": {str(party): {"go": [{"parameters": [parameter]}]}},
                "files": [str(party), str(shapes)],
            })
        )
    )
    record = (
        str(web_dir / "script_stubs.json"),
        json.dumps({str(party): [str(party), str(shapes)]}),
    )

    def stub() -> tuple[str, str]:
        digest = _module_digest(
            party, [str(party), str(shapes)], (web_dir / "package.json").read_bytes()
        )
        return str(party.with_suffix(".pyi")), (
            f"# Generated by Reflex from party.js ({digest}); rewritten when it changes.\n"
            "from builtins import float as _float\n"
            "\n"
            "from reflex_base.event import EventSpec as _EventSpec\n"
            "from reflex_base.vars.base import Var as _Var\n"
            "\n"
            "def go(n: _float | _Var[_float], /) -> _EventSpec: ...\n"
        )

    assert _compile_stubs(modules) == [record, stub()]
    # Unchanged sources keep their stub without reading the types again.
    assert _compile_stubs(modules) == [record]
    # A file the types were read from changed, or is gone: they are read again.
    shapes.write_text('export type Shape = "square";\n')
    assert _compile_stubs(modules) == [record, stub()]
    shapes.unlink()
    assert _compile_stubs(modules) == [record, stub()]
    assert _compile_stubs(modules) == [record]
    # A package upgrade can change the types too.
    (web_dir / "package.json").write_text('{"dependencies": {"a": "2"}}')
    assert _compile_stubs(modules) == [record, stub()]
    assert (web_dir / "script-signatures.js.log").read_text() == f"{party}\n" * 4


def test_compile_script_stubs_removes_stubs_of_modules_no_longer_imported(
    stub_app: tuple[Path, dict[Path, Any]],
):
    """Only stubs Reflex wrote for a module the app stopped importing are removed.

    Args:
        stub_app: the module, and what was read of it.
    """
    party, modules = stub_app
    web_dir = utils.get_web_dir()
    _fake_signatures(
        f"print({json.dumps({'modules': {str(party): {}}, 'files': []})!r})\n"
    )
    # No module and no stub written before: nothing to record.
    assert utils.compile_script_stubs({}) == []
    handwritten = party.with_name("handwritten.pyi")
    handwritten.write_text("def go() -> None: ...\n")
    (web_dir / "script_stubs.json").write_text(
        json.dumps({str(handwritten.with_suffix(".js")): []})
    )
    _compile_stubs(modules)
    stub = party.with_suffix(".pyi")
    assert stub.read_text() == (
        "# Generated by Reflex from party.js "
        f"({_module_digest(party, [str(party)], (web_dir / 'package.json').read_bytes())}); "
        "rewritten when it changes.\n"
        "from typing import Any as _Any\n"
        "\n"
        "from reflex_base.event import EventSpec as _EventSpec\n"
        "\n"
        "def go(*args: _Any) -> _EventSpec: ...\n"
    )

    assert _compile_stubs({}) == [(str(web_dir / "script_stubs.json"), "{}")]
    assert (stub.exists(), handwritten.read_text()) == (
        False,
        "def go() -> None: ...\n",
    )


@pytest.mark.parametrize(
    ("body", "timeout", "detail"),
    [
        (
            (
                "sys.stderr.write(\"Error: Cannot find module 'typescript'\\n\")\n"
                "sys.exit(1)\n"
            ),
            utils._SIGNATURES_TIMEOUT,
            "Error: Cannot find module 'typescript'",
        ),
        (
            "import time\ntime.sleep(30)\n",
            0.5,
            "Command '{command}' timed out after 0.5 seconds",
        ),
    ],
)
def test_compile_script_stubs_warns_when_the_types_cannot_be_read(
    stub_app: tuple[Path, dict[Path, Any]],
    monkeypatch: pytest.MonkeyPatch,
    body: str,
    timeout: float,
    detail: str,
):
    """The stub accepts any arguments, the warning says why, and the next compile retries.

    Args:
        stub_app: the module, and what was read of it.
        monkeypatch: pytest monkeypatch fixture.
        body: the fake signatures script's code.
        timeout: how long the script may run.
        detail: what the warning says went wrong, with ``{command}`` for the
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
    assert _compile_stubs(modules)[1:] == [untyped]
    assert _compile_stubs(modules)[1:] == [untyped]
    command = [sys.executable, "script-signatures.js", str(party)]
    warning = (
        "Reflex could not read the argument types of the JavaScript modules "
        f"{party}, so their type stubs accept any arguments: script-signatures.js "
        f"failed: {detail.format(command=command)}. The app still runs. If this "
        f"repeats, delete {web_dir / 'node_modules'} so that the next run "
        "reinstalls typescript, or report the error at "
        "https://github.com/reflex-dev/reflex/issues."
    )
    assert warnings == [warning, warning]


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
