"""Regression tests for collecting identically named package unit suites."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import toml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "suites", [["first-package"], ["first-package", "second-package"]]
)
def test_package_units_import_their_own_helpers(tmp_path: Path, suites: list[str]):
    """Package-local imports and duplicate filenames work alone and together.

    Args:
        tmp_path: Temporary workspace directory.
        suites: Packages selected for this run.
    """
    config = toml.loads((ROOT / "pyproject.toml").read_text())["tool"]["pytest"]
    (tmp_path / "pyproject.toml").write_text(toml.dumps({"tool": {"pytest": config}}))
    for name in ["first-package", "second-package"]:
        units = tmp_path / "packages" / name / "tests" / "units"
        units.mkdir(parents=True)
        (units / "__init__.py").touch()
        (units / "helpers.py").write_text(f'OWNER = "{name}"\n')
        (units / "test_shared_name.py").write_text(
            "from .helpers import OWNER\n\n"
            f"def test_owner():\n    assert OWNER == {name!r}\n"
        )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *[f"packages/{name}/tests/units" for name in suites],
            "-q",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"{len(suites)} passed" in result.stdout
