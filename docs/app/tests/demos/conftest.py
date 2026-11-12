"""Collect the browser tests written beside the docs demos they exercise.

A ``python test`` block directly below a ``python demo``, ``python demo-only``
or ``python eval`` block holds pytest tests for that demo::

    ```python test
    def test_increment(demo):
        demo.get_by_role("button", name="Increment").click()
        expect(demo.get_by_role("heading")).to_have_text("1")
    ```

The blocks of every compiled docs page are collected here, grouped by the
route the page is served at, as one module per demo. Test blocks may use
``expect``, ``re`` and ``pytest`` without importing them, and these fixtures:

- ``page``: pytest-playwright's page, already at the demo's docs route in the
  app started by reflex-enterprise's ``reflex_app`` fixture.
- ``demo``: a locator for the rendered demo, scrolled into view.

Only the pages under test are compiled, unless ``REFLEX_DOCS_WHITELIST`` is
set (set it empty to compile every page).
"""

import ast
import os
import re
import socket
import types
from dataclasses import dataclass
from pathlib import Path

import pytest
from _pytest.assertion.rewrite import rewrite_asserts
from playwright.sync_api import Locator, Page, expect
from reflex_base.environment import environment
from reflex_docgen.markdown import CodeBlock, parse_document
from reflex_enterprise.testing import AppManager, ReflexApp
from reflex_site_shared.docs.markdown import DEMO_TEST_ATTR, DocDemo, iter_doc_demos

SUITE_PATH = Path(__file__).with_name("test_doc_demos.py")
WHITELIST_ENV = "REFLEX_DOCS_WHITELIST"
# Flags hydration once the backend sends its first event (a socket.io "42" frame):
# the response to the hydrate the client sends with its connection.
_HYDRATION_SCRIPT = """
const NativeWebSocket = window.WebSocket;
window.WebSocket = class extends NativeWebSocket {
  constructor(...args) {
    super(...args);
    this.addEventListener("message", ({ data }) => {
      if (typeof data === "string" && data.startsWith("42")) {
        window.__docsDemoHydrated = true;
      }
    });
  }
};
"""
# Every collected demo, tested or not, for the coverage summary.
_DEMOS_KEY = pytest.StashKey[list["LocatedDemo"]]()


@dataclass(frozen=True)
class LocatedDemo:
    """A demo of a docs page with the markdown lines of its blocks.

    Attributes:
        route: The docs route the demo is rendered at.
        source_path: The markdown file defining the demo.
        demo: The demo and its test blocks.
        index: The demo's index among its document's demos, which the rendered
            demo carries in its ``DEMO_TEST_ATTR``.
        line: The first line of the demo's code (0 if not found).
        test_lines: The first line of each test block's code (0 if not found).
    """

    route: str
    source_path: Path
    demo: DocDemo
    index: int
    line: int
    test_lines: tuple[int, ...]

    @property
    def compiled_route(self) -> str:
        """The route whose compilation builds this demo's page.

        A low-level ``-ll.md`` doc is only built with its high-level page.

        Returns:
            The route to whitelist for this demo.
        """
        if self.source_path.name.endswith("-ll.md"):
            return self.route.removesuffix("low/")
        return self.route


def _locate_demos(route: str, source_path: Path) -> list[LocatedDemo]:
    """Find the demos of a markdown file and the lines their blocks start at.

    Args:
        route: The docs route the file is rendered at.
        source_path: The markdown file.

    Returns:
        The file's demos in document order.
    """
    source = source_path.read_text(encoding="utf-8")
    cursor = 0

    def locate(block: CodeBlock) -> int:
        nonlocal cursor
        index = source.find(block.content, cursor)
        if index < 0:
            return 0
        cursor = index + len(block.content)
        return source.count("\n", 0, index) + 1

    try:
        demos = list(iter_doc_demos(parse_document(source).blocks))
    except ValueError as err:
        err.add_note(f"In {source_path}")
        raise
    located = []
    for index, demo in enumerate(demos):
        line = locate(demo.block)
        test_lines = tuple(locate(test) for test in demo.tests)
        located.append(LocatedDemo(route, source_path, demo, index, line, test_lines))
    return located


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the option listing demos without tests.

    Args:
        parser: The pytest argument parser.
    """
    parser.addoption(
        "--docs-demos-untested",
        action="store_true",
        help="List the docs demos that have no `python test` block and no `notest` flag.",
    )


def pytest_pycollect_makemodule(
    module_path: Path, parent: pytest.Collector
) -> pytest.Collector | None:
    """Collect the docs demo tests in place of the placeholder suite module.

    Args:
        module_path: The python module being collected.
        parent: Its parent collector.

    Returns:
        The docs demo suite for the placeholder module, otherwise None.
    """
    if module_path == SUITE_PATH:
        return DocDemoSuite.from_parent(parent, path=module_path)
    return None


class DocDemoSuite(pytest.File):
    """The docs demo tests, one collector per docs route."""

    def collect(self):
        """Collect every compiled docs route.

        Yields:
            A collector for each docs route.
        """
        from reflex_docs.pages.docs import doc_page_sources

        for route, source_path in sorted(doc_page_sources.items()):
            yield DocRoute.from_parent(self, name=route, source_path=Path(source_path))


class DocRoute(pytest.Collector):
    """The tested demos of one docs route.

    Parsed here rather than by the suite, so a malformed doc fails only its own
    route's collection.
    """

    def __init__(self, *, source_path: Path, **kwargs):
        """Create the collector.

        Args:
            source_path: The markdown file rendered at this route.
            **kwargs: Passed to ``pytest.Collector``.
        """
        super().__init__(**kwargs)
        self.source_path = source_path

    def collect(self):
        """Collect a module per tested demo, named by the markdown line of its code.

        Yields:
            The module of each tested demo.
        """
        demos = _locate_demos(self.name, self.source_path)
        self.config.stash.setdefault(_DEMOS_KEY, []).extend(demos)
        for demo in demos:
            if not demo.demo.tests:
                continue
            name = f"L{demo.line}"
            yield DemoModule.from_parent(
                self,
                path=SUITE_PATH,
                name=name,
                nodeid=f"{self.nodeid}::{name}",
                demo=demo,
            )


class DemoModule(pytest.Module):
    """A module made of the test blocks following one demo."""

    def __init__(self, *, demo: LocatedDemo, **kwargs):
        """Create the module collector.

        Args:
            demo: The demo whose test blocks make up the module.
            **kwargs: Passed to ``pytest.Module``.
        """
        super().__init__(**kwargs)
        self.demo = demo

    def _getobj(self) -> types.ModuleType:
        """Execute the test blocks into a new module.

        Code is compiled against the markdown file at its own line numbers, so
        tracebacks and test locations point into the docs, and asserts are
        rewritten like those of a test module pytest imports.

        Returns:
            The module defining the demo's tests.
        """
        path = str(self.demo.source_path)
        module = types.ModuleType(f"docs_demo_{self.name}")
        module.__file__ = path
        namespace = vars(module)
        namespace.update(expect=expect, pytest=pytest, re=re)
        rewrite = self.config.getoption("assertmode") == "rewrite"
        for test, line in zip(self.demo.demo.tests, self.demo.test_lines, strict=True):
            source = "\n" * (line - 1) + test.content
            tree = ast.parse(source, filename=path)
            if rewrite:
                rewrite_asserts(tree, source.encode(), path, self.config)
            exec(compile(tree, path, "exec"), namespace)
        return module


def _demo_of(request: pytest.FixtureRequest) -> LocatedDemo:
    module = request.node.getparent(DemoModule)
    if module is None:
        msg = f"{request.fixturename} is only available to docs demo tests"
        raise RuntimeError(msg)
    return module.demo


@pytest.fixture(scope="session", autouse=True)
def _configure_docs_app(
    request: pytest.FixtureRequest, reflex_app_manager: AppManager
) -> None:
    """Keep the checkout unchanged and compile only the pages under test.

    The app runs from the docs app directory, so a frontend install would
    otherwise rewrite its committed ``reflex.lock/``; with a whitelist, down to
    the packages of the compiled pages.

    Args:
        request: The pytest fixture request.
        reflex_app_manager: The session manager starting the docs app.
    """
    settings = reflex_app_manager.settings
    extra_env = {
        **settings.extra_env,
        environment.REFLEX_PERSIST_LOCKFILES.name: "false",
    }
    routes = {
        module.demo.compiled_route.rstrip("/")
        for item in request.session.items
        if (module := item.getparent(DemoModule)) is not None
    }
    defaults = {
        WHITELIST_ENV: ",".join(sorted(routes)),
        # Ports the OS hands out lie outside the range dev servers default to,
        # so the app neither collides with them nor follows one to a taken port.
        "REFLEX_FRONTEND_PORT": str(_free_port()),
        "REFLEX_BACKEND_PORT": str(_free_port()),
    }
    for name, value in defaults.items():
        if name not in os.environ and name not in extra_env:
            extra_env[name] = value
    settings.extra_env = extra_env


def _free_port() -> int:
    """Ask the OS for a free port.

    Returns:
        A port nothing listened on when asked.
    """
    with socket.socket() as sock:
        sock.bind(("", 0))
        return sock.getsockname()[1]


@pytest.fixture
def page(page: Page, reflex_app: ReflexApp, request: pytest.FixtureRequest) -> Page:
    """Open the docs route of the demo under test.

    Args:
        page: pytest-playwright's page.
        reflex_app: The running docs app.
        request: The pytest fixture request.

    Returns:
        The page, hydrated at the demo's route.
    """
    page.add_init_script(_HYDRATION_SCRIPT)
    page.goto(reflex_app.url + _demo_of(request).route)
    # Events sent before the backend hydrated the page would be lost.
    page.wait_for_function("() => window.__docsDemoHydrated === true")
    return page


@pytest.fixture
def demo(page: Page, request: pytest.FixtureRequest) -> Locator:
    """Locate the rendered demo the test block follows.

    Args:
        page: The page at the demo's route.
        request: The pytest fixture request.

    Returns:
        A locator for the demo, scrolled into view so deferred demos mount.
    """
    locator = page.locator(f'[{DEMO_TEST_ATTR}="{_demo_of(request).index}"]')
    # The wrapper takes no part in layout, so scroll to the demo's content.
    locator.evaluate("el => el.firstElementChild?.scrollIntoView({block: 'center'})")
    return locator


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, config: pytest.Config
) -> None:
    """Report how many docs demos have tests, listing the rest on request.

    Args:
        terminalreporter: The terminal reporter.
        config: The pytest config.
    """
    demos = config.stash.get(_DEMOS_KEY, [])
    if not demos:
        return
    tested = sum(1 for demo in demos if demo.demo.tests)
    untested = [demo for demo in demos if demo.demo.untested]
    terminalreporter.write_sep("-", "docs demos")
    terminalreporter.write_line(
        f"{tested} of {len(demos)} docs demos have tests, "
        f"{len(demos) - tested - len(untested)} are marked notest"
    )
    # The option is only registered when this conftest is loaded at startup.
    if config.getoption("docs_demos_untested", default=False):
        for demo in untested:
            terminalreporter.write_line(
                f"{demo.source_path}:{demo.line} ({demo.route})"
            )
