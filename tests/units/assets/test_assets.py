import copy
import hashlib
import io
import pickle
import shutil
from collections.abc import Generator
from dataclasses import dataclass
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

    @dataclass
    class _Stat:
        st_size: int
        st_mtime_ns: int

    class _ChangingPath:
        content = b"old"
        stat_calls = 0

        def stat(self) -> _Stat:
            self.stat_calls += 1
            if self.stat_calls == 2:
                self.content = b"final"
                return _Stat(st_size=3, st_mtime_ns=1)
            return _Stat(st_size=len(self.content), st_mtime_ns=2)

        def open(self, mode: str):
            assert mode == "rb"
            return io.BytesIO(self.content)

    monkeypatch.setattr(assets_module, "_HASH_CHUNK_SIZE", 2)
    changing_path = _ChangingPath()

    assert (
        assets_module._short_content_hash(cast(Path, changing_path))
        == hashlib.sha256(b"final").hexdigest()[:8]
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
