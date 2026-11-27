"""Fixtures for the tests of reflex-components-ui."""

import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from reflex_base.config import get_config
from reflex_components_ui.plugin import UIPlugin

# Code for a type checker, kept as text so that no other tool checks it.
FIXTURES = Path(__file__).parent / "style" / "fixtures"


@pytest.fixture
def ui_plugin(monkeypatch: pytest.MonkeyPatch) -> UIPlugin:
    """Configure the plugin, as an app does in its rxconfig.py.

    Args:
        monkeypatch: The pytest fixture that undoes the change.

    Returns:
        The configured plugin.
    """
    plugin = UIPlugin()
    monkeypatch.setattr(get_config(), "plugins", [plugin])
    return plugin


@pytest.fixture
def pyright(tmp_path: Path) -> Callable[[str], list[tuple[int, str, str]]]:
    """Run pyright over a fixture, outside the configuration of the repository.

    Args:
        tmp_path: A directory to copy the fixture to.

    Returns:
        A function from the name of a fixture, without its extension, to the
        line, rule and whole message of every diagnostic.
    """

    def pyright(fixture: str) -> list[tuple[int, str, str]]:
        target = tmp_path / f"{fixture}.py"
        shutil.copy(FIXTURES / f"{fixture}.py.txt", target)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pyright",
                "--outputjson",
                "--pythonpath",
                sys.executable,
                str(target),
            ],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            check=False,
        )
        diagnostics = json.loads(result.stdout)["generalDiagnostics"]
        assert {diagnostic["file"] for diagnostic in diagnostics} <= {str(target)}
        return [
            (
                diagnostic["range"]["start"]["line"] + 1,
                diagnostic["rule"],
                diagnostic["message"],
            )
            for diagnostic in diagnostics
        ]

    return pyright
