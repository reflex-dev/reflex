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
from reflex_base.plugins import CompileContext, CompilerHooks, Plugin
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
        A function from a page, and the plugins of the app to run beside the
        ones of every compile, to its compile context: the source of the page
        is ``compiled_pages["/"].output_code``.
    """

    def compile_page(page: Callable[[], Component], *plugins: Plugin) -> CompileContext:
        ctx = CompileContext(
            pages=[_Page(route="/", component=page)],
            hooks=CompilerHooks(plugins=(*default_page_plugins(), *plugins)),
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
