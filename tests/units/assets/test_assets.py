import shutil
from collections.abc import Generator
from pathlib import Path

import pytest

import reflex as rx
import reflex.constants as constants
from reflex.assets import remove_stale_external_asset_symlinks


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
    # The asset function copies a file to the app's external assets directory.
    asset = rx.asset(path="custom_script.js", shared=True, subfolder="subfolder")
    assert asset == "/external/test_assets/subfolder/custom_script.js"
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
    assert asset == "/external/test_assets/custom_script.js"
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
    assert asset == "/custom_script.js"


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
