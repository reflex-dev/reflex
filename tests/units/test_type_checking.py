"""Run every checker over `tests/type_checking/` and require a clean result."""

import json
import pathlib
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

import pytest

REPO_ROOT = pathlib.Path(__file__).parents[2]
EXAMPLES = REPO_ROOT / "tests" / "type_checking"

# Checked against one version rather than the running interpreter, so the
# asserted types don't drift with whatever Python the suite happens to run on.
PYTHON_VERSION = "3.14"


def _pyright_errors(stdout: str) -> list[str]:
    """Read pyright's JSON output.

    Args:
        stdout: The raw stdout of the pyright run.

    Returns:
        One rendered message per error.
    """
    diagnostics = json.loads(stdout)["generalDiagnostics"]
    return [
        f"{pathlib.Path(d['file']).name}:{d['range']['start']['line'] + 1}: {d['message']}"
        for d in diagnostics
        if d["severity"] == "error"
    ]


def _ty_errors(stdout: str) -> list[str]:
    """Read ty's concise output.

    Args:
        stdout: The raw stdout of the ty run.

    Returns:
        One rendered message per error.
    """
    return [line for line in stdout.splitlines() if "error[" in line]


@dataclass(frozen=True)
class Checker:
    """A type checker invoked over the example directory."""

    name: str
    command: list[str]
    parse: Callable[[str], list[str]]


CHECKERS = (
    Checker(
        name="pyright",
        command=["pyright", "--outputjson", str(EXAMPLES)],
        parse=_pyright_errors,
    ),
    Checker(
        name="ty",
        command=[
            "ty",
            "check",
            "--python-version",
            PYTHON_VERSION,
            "--output-format",
            "concise",
            str(EXAMPLES),
        ],
        parse=_ty_errors,
    ),
)


def test_examples_exist():
    """The suite is worthless if the example directory is empty."""
    assert list(EXAMPLES.glob("*.py")), f"no examples found in {EXAMPLES}"


@pytest.mark.parametrize("checker", CHECKERS, ids=lambda c: c.name)
def test_examples_type_check(checker: Checker):
    """Every example must type-check cleanly.

    Args:
        checker: The checker to run.
    """
    if shutil.which(checker.command[0]) is None:
        pytest.skip(f"{checker.name} is not installed")

    result = subprocess.run(
        checker.command, cwd=REPO_ROOT, capture_output=True, text=True
    )
    errors = checker.parse(result.stdout)
    assert not errors, f"{checker.name} reported {len(errors)} error(s):\n" + "\n".join(
        errors
    )
