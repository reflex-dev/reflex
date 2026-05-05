"""Integration tests for compiler-generated experimental memos."""

import re
from collections.abc import Generator

import pytest
from reflex_base.utils.memo_paths import (
    mirrored_jsx_path,
    mirrored_library_specifier,
    module_to_mirrored_segments,
)
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness

from .utils import poll_for_navigation


def AutoMemoAcrossPagesApp():
    """Reflex app that shares one stateful subtree across two pages."""
    import reflex as rx

    def shared_counter() -> rx.Component:
        return rx.text(rx.State.router.page.raw_path, id="shared-value")

    def index() -> rx.Component:
        return rx.vstack(
            shared_counter(),
            rx.link("Other", href="/other", id="to-other"),
        )

    def other() -> rx.Component:
        return rx.vstack(
            shared_counter(),
            rx.link("Home", href="/", id="to-home"),
        )

    app = rx.App()
    app.add_page(index)
    app.add_page(other, route="/other")


@pytest.fixture
def auto_memo_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start AutoMemoAcrossPagesApp app at tmp_path via AppHarness.

    Yields:
        A running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=AutoMemoAcrossPagesApp,
    ) as harness:
        yield harness


def test_auto_memo_shared_across_pages(auto_memo_app: AppHarness):
    """Shared stateful subtrees compile once and render correctly on both pages."""
    assert auto_memo_app.app_instance is not None, "app is not running"

    web_sources = "\n".join(
        path.read_text() for path in (auto_memo_app.app_path / ".web").rglob("*.jsx")
    )
    assert "$/utils/components" in web_sources
    assert "$/utils/stateful_components" not in web_sources

    driver = auto_memo_app.frontend()
    shared_value = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "shared-value")
    )
    assert auto_memo_app.poll_for_content(shared_value, exp_not_equal="") == "/"

    with poll_for_navigation(driver):
        driver.find_element(By.ID, "to-other").click()

    shared_value = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "shared-value")
    )
    assert "other" in auto_memo_app.poll_for_content(shared_value, exp_not_equal="")


def MultiModuleMemoMirrorApp():
    """Two pages defined in distinct user modules with identical memoizable subtrees.

    Both pages import the same state and render the same button + state-bound
    text, so the auto-memoize plugin assigns identical tags to the wrappers
    on both pages — but each page's wrapper points at its own user module's
    mirrored memo file. This shape regresses against the registry collision
    where the second page's registration overwrote the first.
    """
    from importlib import import_module
    from pathlib import Path

    import reflex as rx

    package_dir = Path(__file__).resolve().parent
    pkg_name = __package__

    state_source = (
        "import reflex as rx\n\n"
        "class MirrorState(rx.State):\n"
        '    value: str = "init"\n\n'
        "    @rx.event\n"
        "    def click(self):\n"
        '        self.value = "clicked"\n'
    )
    page_source = (
        "import reflex as rx\n"
        f"from {pkg_name}.mirror_state import MirrorState\n\n"
        "def page() -> rx.Component:\n"
        "    return rx.vstack(\n"
        '        rx.button("Click", on_click=MirrorState.click, id="mirror-btn"),\n'
        '        rx.text(MirrorState.value, id="mirror-text"),\n'
        "    )\n"
    )

    (package_dir / "mirror_state.py").write_text(state_source)
    (package_dir / "mirror_page_a.py").write_text(page_source)
    (package_dir / "mirror_page_b.py").write_text(page_source)

    page_a = import_module(f"{pkg_name}.mirror_page_a")
    page_b = import_module(f"{pkg_name}.mirror_page_b")

    app = rx.App()
    app.add_page(page_a.page, route="/page-a")
    app.add_page(page_b.page, route="/page-b")


@pytest.fixture
def multi_module_memo_app(
    app_harness_env, tmp_path
) -> Generator[AppHarness, None, None]:
    """Start MultiModuleMemoMirrorApp under both dev and prod harnesses.

    The prod harness runs a real vite/rolldown bundle of every route, so if
    any route imports a memo tag that no module exports, fixture setup fails
    with the same ``MISSING_EXPORT`` error the docs CI produced. The dev
    harness runs the same Reflex compile but skips the prod bundler.

    Yields:
        A running AppHarness (or AppHarnessProd) instance for the app.
    """
    with app_harness_env.create(
        root=tmp_path,
        app_source=MultiModuleMemoMirrorApp,
    ) as harness:
        yield harness


_MIRRORED_IMPORT_RE = re.compile(r'import\s*\{([^}]+)\}\s*from\s*"\$/([^"]+)"')


def _imports_from_mirrored_module(page_jsx: str, mirrored_path: str) -> set[str]:
    """Return the named imports a page module pulls from a mirrored memo file."""
    imports: set[str] = set()
    for match in _MIRRORED_IMPORT_RE.finditer(page_jsx):
        if match.group(2) != mirrored_path:
            continue
        for raw in match.group(1).split(","):
            name = raw.strip()
            if name:
                imports.add(name)
    return imports


def test_multi_module_memo_mirror_emits_per_user_module(
    multi_module_memo_app: AppHarness,
):
    """Each user module gets its own mirrored memo file with the shared export.

    Regression: when the same memoizable subtree appeared on pages defined in
    distinct user modules, the auto-memo registry — keyed only by tag — kept
    one definition. Only that source module's mirrored memo file was written,
    leaving the other page importing exports from a JSX file that never
    declared them. Build (or page navigation) failed with ``MISSING_EXPORT``.
    """
    assert multi_module_memo_app.app_instance is not None, "app is not running"

    web_dir = multi_module_memo_app.app_path / ".web"
    app_pkg = multi_module_memo_app.app_name

    # Static routes are emitted as ``[<route-part>]._index.jsx``.
    page_a_jsx = next(
        (web_dir / "app" / "routes").rglob("*page-a*_index.jsx"),
        None,
    )
    page_b_jsx = next(
        (web_dir / "app" / "routes").rglob("*page-b*_index.jsx"),
        None,
    )
    assert page_a_jsx is not None, "page-a route output not found"
    assert page_b_jsx is not None, "page-b route output not found"

    segments_a = module_to_mirrored_segments(f"{app_pkg}.mirror_page_a")
    segments_b = module_to_mirrored_segments(f"{app_pkg}.mirror_page_b")
    assert segments_a is not None
    assert segments_b is not None
    mirror_a_jsx = mirrored_jsx_path(web_dir, segments_a)
    mirror_b_jsx = mirrored_jsx_path(web_dir, segments_b)
    assert mirror_a_jsx.exists(), (
        f"mirrored memo file for module a not emitted at {mirror_a_jsx}"
    )
    assert mirror_b_jsx.exists(), (
        f"mirrored memo file for module b not emitted at {mirror_b_jsx}"
    )

    # ``mirrored_library_specifier`` returns ``$/<segments>``; the regex captures
    # group 2 already strips the ``$/`` prefix, so match against the bare path.
    spec_a = mirrored_library_specifier(segments_a).removeprefix("$/")
    spec_b = mirrored_library_specifier(segments_b).removeprefix("$/")
    imports_from_a = _imports_from_mirrored_module(page_a_jsx.read_text(), spec_a)
    imports_from_b = _imports_from_mirrored_module(page_b_jsx.read_text(), spec_b)
    assert imports_from_a, "page-a does not import from its mirrored memo file"
    assert imports_from_b, "page-b does not import from its mirrored memo file"
    # Identical subtrees → identical wrapper tags across the two pages.
    assert imports_from_a == imports_from_b, (
        "expected the same memo wrapper tags on both pages, "
        f"got {imports_from_a} vs {imports_from_b}"
    )

    mirror_a_code = mirror_a_jsx.read_text()
    mirror_b_code = mirror_b_jsx.read_text()
    for tag in imports_from_a:
        assert f"export const {tag} = memo" in mirror_a_code, (
            f"{mirror_a_jsx.name} is missing `export const {tag}`"
        )
        assert f"export const {tag} = memo" in mirror_b_code, (
            f"{mirror_b_jsx.name} is missing `export const {tag}`"
        )
