"""Tests for the array comparison helper shipped in the web template."""

import shutil
import subprocess
from pathlib import Path

import pytest
import reflex_base

ARRAY_HELPER_PATH = (
    Path(reflex_base.__file__).parent
    / ".templates"
    / "web"
    / "utils"
    / "helpers"
    / "array.js"
)


@pytest.mark.skipif(shutil.which("node") is None, reason="node missing")
def test_compare_arrays_matches_python_list_semantics():
    """Run the node test suite for compareArrays against the real template."""
    result = subprocess.run(
        [
            "node",
            str(Path(__file__).with_name("array_helper.test.mjs")),
            str(ARRAY_HELPER_PATH),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
