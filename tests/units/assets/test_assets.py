import copy
import hashlib
import io
import itertools
import logging
import os
import pickle
import shutil
import threading
from collections.abc import Callable, Generator
from pathlib import Path
from typing import cast

import pytest

import reflex as rx
import reflex.constants as constants
from reflex.assets import AssetPathStr, remove_stale_external_asset_symlinks


def _asset_hash(path: Path) -> str:
    """Return the expected short content hash for an asset."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


@pytest.fixture
def mock_asset_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a mock asset file and patch the current working directory.

    Args:
        tmp_path: A temporary directory provided by pytest.
        monkeypatch: A pytest fixture for patching.

    Returns:
        The path to a tmp cwd that will be used for assets.
    """
    # Create a temporary directory to act as the current working directory.
    mock_cwd = tmp_path / "mock_asset_path"
    mock_cwd.mkdir()
    monkeypatch.chdir(mock_cwd)

    return mock_cwd


def test_shared_asset(mock_asset_path: Path) -> None:
    """Test shared assets."""
    source_file = Path(__file__).parent / "custom_script.js"
    expected_hash = _asset_hash(source_file)

    # The asset function copies a file to the app's external assets directory.
    asset = rx.asset(path="custom_script.js", shared=True, subfolder="subfolder")
    assert (
        asset == f"/external/test_assets/subfolder/custom_script.js?v={expected_hash}"
    )
    result_file = Path(
        mock_asset_path,
        "assets",
        "external",
        "test_assets",
        "subfolder",
        "custom_script.js",
    )
    assert result_file.exists()

    # Running a second time should not raise an error.
    asset = rx.asset(path="custom_script.js", shared=True, subfolder="subfolder")

    # Test the asset function without a subfolder.
    asset = rx.asset(path="custom_script.js", shared=True)
    assert asset == f"/external/test_assets/custom_script.js?v={expected_hash}"
    result_file = Path(
        mock_asset_path, "assets", "external", "test_assets", "custom_script.js"
    )
    assert result_file.exists()

    # clean up
    shutil.rmtree(Path(mock_asset_path) / "assets" / "external")

    with pytest.raises(FileNotFoundError):
        asset = rx.asset("non_existent_file.js")

    # Nothing is done to assets when file does not exist.
    assert not Path(mock_asset_path / "assets" / "external").exists()


def _shared_dst_file(mock_asset_path: Path) -> Path:
    """Return the symlink `rx.asset(shared=True)` creates for this test module.

    Args:
        mock_asset_path: The mock current working directory.

    Returns:
        The path of the symlink in the app's external assets directory.
    """
    return (
        mock_asset_path
        / constants.Dirs.APP_ASSETS
        / constants.Dirs.EXTERNAL_APP_ASSETS
        / "test_assets"
        / "custom_script.js"
    )


_REAL_SYMLINK = os.symlink


def _competitor_links(dst_file: Path, target: Path) -> None:
    """Have the competing process point `dst_file` at `target`.

    Args:
        dst_file: The destination the competitor writes to.
        target: The file the competitor links to.
    """
    dst_file.unlink(missing_ok=True)
    _REAL_SYMLINK(target, dst_file)


def _simulate_competing_process(
    monkeypatch: pytest.MonkeyPatch,
    script: list[tuple[Callable[[], None], Callable[[], None]]],
) -> None:
    """Run another process's writes around each `os.symlink` call.

    Models a second app compiling into the same working directory: each entry
    of `script` is a (before, after) pair applied around the n-th symlink call,
    so the competitor can create, remove or repoint the destination inside the
    window a check-then-act implementation depends on. The last entry is reused
    once the script is exhausted.

    Args:
        monkeypatch: A pytest fixture for patching.
        script: The (before, after) callbacks to apply to successive calls.
    """
    real_symlink = os.symlink
    calls = itertools.count()

    def fake_symlink(target, path, *args, **kwargs):
        before, after = script[min(next(calls), len(script) - 1)]
        before()
        try:
            return real_symlink(target, path, *args, **kwargs)
        finally:
            after()

    monkeypatch.setattr(os, "symlink", fake_symlink)


def test_shared_asset_survives_concurrent_removal(
    mock_asset_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A competitor that creates then removes the link must not break `asset()`.

    Regression test: the destination existing when we link and being gone again
    when we clean up used to escape as `FileNotFoundError` from `dst_file.unlink()`.

    Args:
        mock_asset_path: The mock current working directory.
        monkeypatch: A pytest fixture for patching.
    """
    source_file = Path(__file__).parent / "custom_script.js"
    dst_file = _shared_dst_file(mock_asset_path)
    decoy = mock_asset_path / "decoy.js"
    decoy.write_text("decoy")

    _simulate_competing_process(
        monkeypatch,
        [
            (
                lambda: _competitor_links(dst_file, decoy),
                lambda: dst_file.unlink(missing_ok=True),
            )
        ],
    )

    asset = rx.asset(path="custom_script.js", shared=True)

    assert (
        asset == f"/external/test_assets/custom_script.js?v={_asset_hash(source_file)}"
    )
    assert dst_file.is_symlink()
    assert dst_file.resolve() == source_file.resolve()


def test_shared_asset_survives_concurrent_recreation(
    mock_asset_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A competitor recreating the link on every attempt must not break `asset()`.

    Regression test: the retry after `FileExistsError` used to raise a second,
    unhandled `FileExistsError` when the destination reappeared in between.

    Args:
        mock_asset_path: The mock current working directory.
        monkeypatch: A pytest fixture for patching.
    """
    source_file = Path(__file__).parent / "custom_script.js"
    dst_file = _shared_dst_file(mock_asset_path)
    decoy = mock_asset_path / "decoy.js"
    decoy.write_text("decoy")

    _simulate_competing_process(
        monkeypatch, [(lambda: _competitor_links(dst_file, decoy), lambda: None)]
    )

    rx.asset(path="custom_script.js", shared=True)

    assert dst_file.is_symlink()
    assert dst_file.resolve() == source_file.resolve()


@pytest.mark.parametrize("existing", ["symlink_to_decoy", "regular_file"])
def test_shared_asset_converges_on_correct_target(
    mock_asset_path: Path, existing: str
) -> None:
    """An existing destination is repointed at the asset rather than trusted.

    Args:
        mock_asset_path: The mock current working directory.
        existing: What another process left at the destination.
    """
    source_file = Path(__file__).parent / "custom_script.js"
    dst_file = _shared_dst_file(mock_asset_path)
    dst_file.parent.mkdir(parents=True, exist_ok=True)
    if existing == "symlink_to_decoy":
        decoy = mock_asset_path / "decoy.js"
        decoy.write_text("decoy")
        dst_file.symlink_to(decoy)
    else:
        dst_file.write_text("stale copy")

    rx.asset(path="custom_script.js", shared=True)

    assert dst_file.is_symlink()
    assert dst_file.resolve() == source_file.resolve()
    assert dst_file.read_text() == source_file.read_text()


def test_shared_asset_is_thread_safe(mock_asset_path: Path) -> None:
    """Concurrent `asset()` calls for the same file all succeed.

    Args:
        mock_asset_path: The mock current working directory.
    """
    source_file = Path(__file__).parent / "custom_script.js"
    dst_file = _shared_dst_file(mock_asset_path)
    errors: list[BaseException] = []
    start = threading.Barrier(8)

    def compile_once() -> None:
        start.wait()
        try:
            for _ in range(25):
                rx.asset(path="custom_script.js", shared=True)
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=compile_once) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert dst_file.is_symlink()
    assert dst_file.resolve() == source_file.resolve()
    # No temporary link is left behind in the destination directory.
    assert [p.name for p in dst_file.parent.iterdir()] == ["custom_script.js"]


@pytest.mark.parametrize(
    ("path", "shared"),
    [
        pytest.param("non_existing_file", True),
        pytest.param("non_existing_file", False),
    ],
)
def test_invalid_assets(path: str, shared: bool) -> None:
    """Test that asset raises an error when the file does not exist.

    Args:
        path: The path to the asset.
        shared: Whether the asset should be shared.
    """
    with pytest.raises(FileNotFoundError):
        _ = rx.asset(path, shared=shared)


@pytest.fixture
def custom_script_in_asset_dir(mock_asset_path: Path) -> Generator[Path, None, None]:
    """Create a custom_script.js file in the app's assets directory.

    Yields:
        The path to the custom_script.js file.
    """
    asset_dir = mock_asset_path / constants.Dirs.APP_ASSETS
    asset_dir.mkdir(exist_ok=True)
    path = asset_dir / "custom_script.js"
    path.touch()
    yield path
    path.unlink()


def test_local_asset(custom_script_in_asset_dir: Path) -> None:
    """Test that no error is raised if shared is set and both files exist.

    Args:
        custom_script_in_asset_dir: Fixture that creates a custom_script.js file in the app's assets directory.

    """
    asset = rx.asset("custom_script.js", shared=False)
    assert asset == f"/custom_script.js?v={_asset_hash(custom_script_in_asset_dir)}"


def test_local_asset_hash_changes_with_content(
    custom_script_in_asset_dir: Path,
) -> None:
    """The asset URL changes when the file content changes.

    Args:
        custom_script_in_asset_dir: Fixture that creates a custom_script.js file in the app's assets directory.
    """
    custom_script_in_asset_dir.write_text("first")
    first_asset = rx.asset("custom_script.js", shared=False)

    custom_script_in_asset_dir.write_text("second")
    second_asset = rx.asset("custom_script.js", shared=False)

    assert first_asset != second_asset
    assert first_asset == (
        f"/custom_script.js?v={hashlib.sha256(b'first').hexdigest()[:8]}"
    )
    assert second_asset == (
        f"/custom_script.js?v={hashlib.sha256(b'second').hexdigest()[:8]}"
    )


def test_asset_hash_reads_in_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hashing handles assets larger than one read chunk.

    Args:
        tmp_path: A temporary directory provided by pytest.
        monkeypatch: A pytest fixture for patching.
    """
    import reflex.assets as assets_module

    monkeypatch.setattr(assets_module, "_HASH_CHUNK_SIZE", 3)
    asset_file = tmp_path / "large.bin"
    asset_file.write_bytes(b"abcdefghi")

    assert (
        assets_module._short_content_hash(asset_file)
        == hashlib.sha256(b"abcdefghi").hexdigest()[:8]
    )


def test_asset_hash_retries_when_file_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hashing retries when the file changes while it is being read.

    Args:
        monkeypatch: A pytest fixture for patching.
    """
    import reflex.assets as assets_module

    class _ChangingPath:
        open_calls = 0

        def open(self, mode: str) -> io.BytesIO:
            assert mode == "rb"
            self.open_calls += 1
            if self.open_calls == 1:
                return io.BytesIO(b"old")
            return io.BytesIO(b"final")

    monkeypatch.setattr(assets_module, "_HASH_CHUNK_SIZE", 2)
    changing_path = _ChangingPath()

    assert (
        assets_module._short_content_hash(cast(Path, changing_path))
        == hashlib.sha256(b"final").hexdigest()[:8]
    )
    assert changing_path.open_calls == 4


def test_asset_hash_retries_after_atomic_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hashing retries if the file is replaced with the same size and mtime.

    Args:
        monkeypatch: A pytest fixture for patching.
    """
    import reflex.assets as assets_module

    class _ReplacingPath:
        open_calls = 0

        def open(self, mode: str) -> io.BytesIO:
            assert mode == "rb"
            self.open_calls += 1
            if self.open_calls == 1:
                return io.BytesIO(b"old")
            return io.BytesIO(b"new")

    monkeypatch.setattr(assets_module, "_HASH_CHUNK_SIZE", 2)
    replacing_path = _ReplacingPath()

    assert (
        assets_module._short_content_hash(cast(Path, replacing_path))
        == hashlib.sha256(b"new").hexdigest()[:8]
    )
    assert replacing_path.open_calls == 4


def test_asset_hash_retries_after_in_place_rewrite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hashing retries if an in-place rewrite changes bytes but preserves metadata.

    Args:
        monkeypatch: A pytest fixture for patching.
    """
    import reflex.assets as assets_module

    class _RewritingPath:
        open_calls = 0
        reads = [b"oldnew", b"newnew", b"newnew", b"newnew"]

        def open(self, mode: str) -> io.BytesIO:
            assert mode == "rb"
            self.open_calls += 1
            return io.BytesIO(self.reads[self.open_calls - 1])

    monkeypatch.setattr(assets_module, "_HASH_CHUNK_SIZE", 3)
    rewriting_path = _RewritingPath()

    assert (
        assets_module._short_content_hash(cast(Path, rewriting_path))
        == hashlib.sha256(b"newnew").hexdigest()[:8]
    )
    assert rewriting_path.open_calls == 4


def test_asset_hash_uses_timestamp_when_file_never_stabilizes(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Hashing falls back to a timestamp if every read sees a file change.

    Args:
        monkeypatch: A pytest fixture for patching.
        caplog: Pytest log capture fixture.
    """
    import reflex.assets as assets_module

    class _ChangingPath:
        open_calls = 0

        def open(self, mode: str) -> io.BytesIO:
            assert mode == "rb"
            self.open_calls += 1
            return io.BytesIO(str(self.open_calls).encode())

    monkeypatch.setattr(assets_module.time, "time", lambda: 1234.5)

    result = assets_module._short_content_hash(cast(Path, _ChangingPath()))

    assert result == "1234.5"
    warn_calls = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warn_calls) == 1
    assert (
        warn_calls[0]
        .getMessage()
        .endswith(
            f"was modified {assets_module._MAX_HASH_ATTEMPTS} times while calculating hash."
        )
    )


def test_asset_importable_path_local(custom_script_in_asset_dir: Path) -> None:
    """A local asset path exposes an `importable_path` prefixed with $/public.

    Args:
        custom_script_in_asset_dir: Fixture that creates a custom_script.js file in the app's assets directory.
    """
    asset = rx.asset("custom_script.js", shared=False)
    assert asset == f"/custom_script.js?v={_asset_hash(custom_script_in_asset_dir)}"
    assert isinstance(asset, AssetPathStr)
    assert asset.importable_path == "$/public/custom_script.js"


def test_asset_importable_path_shared(mock_asset_path: Path) -> None:
    """A shared asset path exposes an `importable_path` prefixed with $/public."""
    asset = rx.asset(path="custom_script.js", shared=True)
    expected_hash = _asset_hash(Path(__file__).parent / "custom_script.js")
    assert asset == f"/external/test_assets/custom_script.js?v={expected_hash}"
    assert isinstance(asset, AssetPathStr)
    assert asset.importable_path == "$/public/external/test_assets/custom_script.js"


def test_asset_importable_path_with_frontend_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With frontend_path configured, str value is prefixed but importable_path is not.

    Args:
        monkeypatch: A pytest fixture for patching.
    """
    import reflex.assets as assets_module

    class _StubConfig:
        frontend_path = "/my-app"

        @staticmethod
        def prepend_frontend_path(path: str) -> str:
            return f"/my-app{path}" if path.startswith("/") else path

    monkeypatch.setattr(assets_module, "get_config", lambda: _StubConfig)

    asset = AssetPathStr("/external/mod/custom_script.js")
    assert asset == "/my-app/external/mod/custom_script.js"
    assert asset.importable_path == "$/public/external/mod/custom_script.js"

    # Bytes + encoding form (matches str() signature) also works.
    asset_from_bytes = AssetPathStr(b"/external/mod/file.js", "utf-8")
    assert asset_from_bytes == "/my-app/external/mod/file.js"
    assert asset_from_bytes.importable_path == "$/public/external/mod/file.js"


def test_asset_path_pickle_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pickle/copy round-trips must not double-apply the frontend prefix.

    Regression test for https://github.com/reflex-dev/reflex/pull/6348#discussion_r3113958087.

    Args:
        monkeypatch: A pytest fixture for patching.
    """
    import reflex.assets as assets_module

    class _StubConfig:
        frontend_path = "/my-app"

        @staticmethod
        def prepend_frontend_path(path: str) -> str:
            return f"/my-app{path}" if path.startswith("/") else path

    monkeypatch.setattr(assets_module, "get_config", lambda: _StubConfig)

    original = AssetPathStr("/external/mod/file.js")
    assert original == "/my-app/external/mod/file.js"
    assert original.importable_path == "$/public/external/mod/file.js"

    for clone in (
        pickle.loads(pickle.dumps(original)),
        copy.copy(original),
        copy.deepcopy(original),
    ):
        assert isinstance(clone, AssetPathStr)
        assert clone == "/my-app/external/mod/file.js"
        assert clone.importable_path == "$/public/external/mod/file.js"


def test_versioned_asset_path_pickle_roundtrip(
    custom_script_in_asset_dir: Path,
) -> None:
    """Pickle/copy round-trips preserve the versioned URL and unversioned import path.

    Args:
        custom_script_in_asset_dir: Fixture that creates a custom_script.js file in the app's assets directory.
    """
    original = rx.asset("custom_script.js")
    assert original == f"/custom_script.js?v={_asset_hash(custom_script_in_asset_dir)}"
    assert original.importable_path == "$/public/custom_script.js"

    for clone in (
        pickle.loads(pickle.dumps(original)),
        copy.copy(original),
        copy.deepcopy(original),
    ):
        assert isinstance(clone, AssetPathStr)
        assert clone == original
        assert clone.importable_path == original.importable_path


def test_remove_stale_external_asset_symlinks(mock_asset_path: Path) -> None:
    """Test that stale symlinks and empty dirs in assets/external/ are cleaned up."""
    external_dir = (
        mock_asset_path / constants.Dirs.APP_ASSETS / constants.Dirs.EXTERNAL_APP_ASSETS
    )

    # Set up: create a subdirectory with a broken symlink.
    stale_dir = external_dir / "old_module" / "subpkg"
    stale_dir.mkdir(parents=True, exist_ok=True)
    stale_symlink = stale_dir / "missing_file.js"
    stale_symlink.symlink_to("/nonexistent/path/missing_file.js")
    assert stale_symlink.is_symlink()
    assert not stale_symlink.resolve().exists()

    # Also create a valid symlink that should be preserved.
    valid_dir = external_dir / "valid_module"
    valid_dir.mkdir(parents=True, exist_ok=True)
    valid_target = Path(__file__).parent / "custom_script.js"
    valid_symlink = valid_dir / "custom_script.js"
    valid_symlink.symlink_to(valid_target)
    assert valid_symlink.is_symlink()
    assert valid_symlink.resolve().exists()

    remove_stale_external_asset_symlinks()

    # Broken symlink and its empty parent dirs should be removed.
    assert not stale_symlink.exists()
    assert not stale_symlink.is_symlink()
    assert not stale_dir.exists()
    assert not (external_dir / "old_module").exists()

    # Valid symlink should be preserved.
    assert valid_symlink.is_symlink()
    assert valid_symlink.resolve().exists()


def test_remove_stale_symlinks_no_external_dir(mock_asset_path: Path) -> None:
    """Test that cleanup is a no-op when assets/external/ doesn't exist."""
    external_dir = (
        mock_asset_path / constants.Dirs.APP_ASSETS / constants.Dirs.EXTERNAL_APP_ASSETS
    )
    assert not external_dir.exists()
    # Should not raise.
    remove_stale_external_asset_symlinks()
