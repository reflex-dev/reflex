import shutil
from pathlib import Path

import pytest

import reflex as rx


def test_asset():
    # Test the asset function.

    # The asset function copies a file to the app's external assets directory.
    asset = rx._x.asset("custom_script.js", "subfolder")
    assert asset == "/external/test_assets/subfolder/custom_script.js"
    result_file = Path(
        Path.cwd(), "assets/external/test_assets/subfolder/custom_script.js"
    )
    assert result_file.exists()

    # Running a second time should not raise an error.
    asset = rx._x.asset("custom_script.js", "subfolder")

    # Test the asset function without a subfolder.
    asset = rx._x.asset("custom_script.js")
    assert asset == "/external/test_assets/custom_script.js"
    result_file = Path(Path.cwd(), "assets/external/test_assets/custom_script.js")
    assert result_file.exists()

    # clean up
    shutil.rmtree(Path.cwd() / "assets/external")

    with pytest.raises(FileNotFoundError):
        asset = rx._x.asset("non_existent_file.js")

    # Nothing is done to assets when file does not exist.
    assert not Path(Path.cwd() / "assets/external").exists()
