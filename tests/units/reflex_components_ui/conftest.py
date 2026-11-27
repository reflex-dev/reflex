"""Fixtures for the tests of reflex-components-ui."""

import dataclasses
from collections.abc import Callable
from typing import Any

import pytest
from reflex_base.components.component import Component
from reflex_base.config import get_config
from reflex_base.plugins import CompileContext, CompilerHooks
from reflex_components_ui.plugin import UIPlugin

from reflex.compiler.plugins import default_page_plugins


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
