"""Fixtures for the tests of reflex-components-ui."""

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from reflex_base.components.component import Component
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
            # Pyright writes UTF-8 whatever the encoding of the system is.
            encoding="utf-8",
            cwd=tmp_path,
            check=False,
        )
        diagnostics = json.loads(result.stdout)["generalDiagnostics"]
        # Pyright names a Windows drive in lower case.
        assert {os.path.normcase(diagnostic["file"]) for diagnostic in diagnostics} <= {
            os.path.normcase(target)
        }
        return [
            (
                diagnostic["range"]["start"]["line"] + 1,
                diagnostic["rule"],
                diagnostic["message"],
            )
            for diagnostic in diagnostics
        ]

    return pyright


@pytest.fixture
def compiled() -> Callable[[Component], Component]:
    """Give a component the styles a compile adds to it.

    Returns:
        A function from a component to itself, with the styles of its
        ``add_style``.
    """

    def compiled(component: Component) -> Component:
        component._add_style_recursive({})
        return component

    return compiled


@pytest.fixture
def declared_styles() -> Callable[[Any], list[dict[str, Any]]]:
    """Collect the style each rx.ui element of a tree declares.

    Returns:
        A function from the root of a tree to the lowered style of each of
        its rx.ui elements, parents before children.
    """

    def declared_styles(component: Any) -> list[dict[str, Any]]:
        found = []
        element_styles = getattr(component, "_element_styles", None)
        if element_styles is not None:
            found.append(element_styles().style.style)
        for child in getattr(component, "children", ()):
            found.extend(declared_styles(child))
        return found

    return declared_styles
