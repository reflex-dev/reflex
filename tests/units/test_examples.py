"""Unit tests for the import rules of the examples/ directory."""

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _reflex_imports_not_as_rx(source: str) -> list[int]:
    """Find the imports of reflex written other than ``import reflex as rx``.

    Args:
        source: The Python source to inspect.

    Returns:
        The line numbers of those imports.
    """
    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported = [(alias.name, alias.asname) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            imported = [(node.module, None)]
        else:
            continue
        if any(
            name.partition(".")[0] == "reflex" and (name, asname) != ("reflex", "rx")
            for name, asname in imported
        ):
            lines.append(node.lineno)
    return lines


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


@pytest.mark.parametrize(
    ("source", "lines"),
    [
        ("import reflex as rx\n", []),
        ("import os, reflex as rx\nfrom . import state\nimport reflexive\n", []),
        ("import reflex\n", [1]),
        ("import reflex as r\n", [1]),
        ("import reflex.state\n", [1]),
        ("from reflex import App\n", [1]),
        ("import reflex as rx\nfrom reflex.state import State\n", [2]),
    ],
)
def test_reflex_imports_not_as_rx(source: str, lines: list[int]):
    assert _reflex_imports_not_as_rx(source) == lines


def test_examples_import_reflex_only_as_rx():
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "examples/*.py"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    offenders = {
        path: lines
        for path in filter(None, tracked)
        if (lines := _reflex_imports_not_as_rx((REPO_ROOT / path).read_text("utf-8")))
    }
    assert not offenders, "examples import reflex only as `import reflex as rx`"
