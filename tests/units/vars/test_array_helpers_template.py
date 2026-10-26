"""Regression tests for the array.js comparison helper."""

import shutil
import subprocess
from pathlib import Path

import pytest

ARRAY_HELPERS_TEMPLATE = (
    Path(__file__).parents[3]
    / "packages/reflex-base/src/reflex_base/.templates/web/utils/helpers/array.js"
)


def test_compare_arrays_matches_python_list_semantics() -> None:
    """Execute the helper behavior tests against the real template module."""
    assert ARRAY_HELPERS_TEMPLATE.is_file()
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the frontend runtime tests")
        return
    result = subprocess.run(
        [
            node,
            "--experimental-vm-modules",
            str(Path(__file__).with_name("array_helpers.test.mjs")),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
