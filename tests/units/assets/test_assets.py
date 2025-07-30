import shutil
from collections.abc import Generator
from pathlib import Path

import pytest

import reflex as rx
import reflex.constants as constants


def test_shared_asset() -> None:
    """Test shared assets."""
    # The asset function copies a file to the app's external assets directory.
    asset = rx.asset(path="custom_script.js", shared=True, subfolder="subfolder")
    assert asset == "/external/test_assets/subfolder/custom_script.js"
    result_file = Path(
        Path.cwd(), "assets/external/test_assets/subfolder/custom_script.js"
    )
    assert result_file.exists()

    # Running a second time should not raise an error.
    asset = rx.asset(path="custom_script.js", shared=True, subfolder="subfolder")

    # Test the asset function without a subfolder.
    asset = rx.asset(path="custom_script.js", shared=True)
    assert asset == "/external/test_assets/custom_script.js"
    result_file = Path(Path.cwd(), "assets/external/test_assets/custom_script.js")
    assert result_file.exists()

    # clean up
    shutil.rmtree(Path.cwd() / "assets/external")

    with pytest.raises(FileNotFoundError):
        asset = rx.asset("non_existent_file.js")

    # Nothing is done to assets when file does not exist.
    assert not Path(Path.cwd() / "assets/external").exists()


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
def custom_script_in_asset_dir() -> Generator[Path, None, None]:
    """Create a custom_script.js file in the app's assets directory.

    Yields:
        The path to the custom_script.js file.
    """
    asset_dir = Path.cwd() / constants.Dirs.APP_ASSETS
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
