"""Unit tests for the lint configuration of the examples/ directory (examples/ruff.toml)."""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _ruff_banned_imports(source: str, filename: Path) -> list[str]:
    """Run ruff's banned-api rule on a source snippet.

    Args:
        source: The Python source to lint.
        filename: The path ruff resolves its configuration for.

    Returns:
        The banned module names ruff reports, in source order.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--no-cache",
            "--select",
            "TID251",
            "--output-format",
            "concise",
            "--stdin-filename",
            str(filename),
            "-",
        ],
        input=source,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    return re.findall(r"`([\w.]+)` is banned", result.stdout)


def test_examples_import_only_reflex():
    split_packages = sorted(
        module.name
        for module in REPO_ROOT.glob("packages/*/src/*")
        if (module / "__init__.py").is_file()
    )
    source = "import reflex as rx\n" + "".join(
        f"import {name}.submodule\n" for name in split_packages
    )
    banned = _ruff_banned_imports(source, REPO_ROOT / "examples" / "app" / "app.py")
    assert banned == split_packages, (
        "each package under packages/ needs a banned-api entry in examples/ruff.toml"
    )


def test_split_packages_are_allowed_outside_examples():
    source = "from reflex_base.utils import console\n"
    assert not _ruff_banned_imports(source, REPO_ROOT / "reflex" / "app.py")
