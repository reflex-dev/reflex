"""Fixtures for the tests of reflex-components-ui."""

import dataclasses
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from reflex_base.components.component import Component
from reflex_base.config import get_config
from reflex_base.plugins import CompileContext, CompilerHooks
from reflex_components_ui.plugin import UIPlugin

from reflex.compiler.plugins import default_page_plugins

# Code for a type checker, kept as text so that no other tool checks it.
FIXTURES = Path(__file__).parent / "style" / "fixtures"


@dataclasses.dataclass(slots=True)
class _Page:
    route: str
    component: Callable[[], Component]
    title: Any = None
    description: Any = None
    image: str = ""
    meta: tuple[dict[str, Any], ...] = ()
    _source_module: str | None = None


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
def compile_page(preserve_memo_registries: None) -> Callable[..., CompileContext]:
    """Compile a page the way an app compile does.

    Args:
        preserve_memo_registries: Restores the memos a compile registers.

    Returns:
        A function from a page to its compile context: the source of the page
        is ``compiled_pages["/"].output_code``.
    """

    def compile_page(page: Callable[[], Component]) -> CompileContext:
        ctx = CompileContext(
            pages=[_Page(route="/", component=page)],
            hooks=CompilerHooks(plugins=default_page_plugins()),
        )
        with ctx:
            ctx.compile()
        return ctx

    return compile_page


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
