"""Integration tests for compiler-generated experimental memos."""

import re
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

_MEMO_IMPORT = re.compile(
    r'^import \{([^}]*)\} from "(\$/utils/components/[^"]+)"$', re.MULTILINE
)


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
    """Start the shared-component app.

    Args:
        tmp_path: pytest tmp_path fixture.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=AutoMemoAcrossPagesApp,
    ) as harness:
        yield harness


def test_auto_memo_shared_across_pages(auto_memo_app: AppHarness, page: Page):
    """A shared stateful subtree renders correctly on both pages.

    Args:
        auto_memo_app: harness for the shared-component app.
        page: Playwright page.
    """
    assert auto_memo_app.app_instance is not None, "app is not running"

    web_dir = auto_memo_app.app_path / ".web"
    web_sources = "\n".join(path.read_text() for path in web_dir.rglob("*.jsx"))
    assert "$/utils/stateful_components" not in web_sources
    # Each page imports the shared memo from its own route module.
    memo_imports = {
        path.name: _MEMO_IMPORT.findall(path.read_text())
        for path in (web_dir / "app" / "routes").glob("*.jsx")
    }
    ((tag, _),) = memo_imports["_index.jsx"]
    assert memo_imports == {
        "[404]._index.jsx": [],
        "[other]._index.jsx": [(tag, "$/utils/components/routes/[other]._index")],
        "_index.jsx": [(tag, "$/utils/components/routes/_index")],
    }

    assert auto_memo_app.frontend_url is not None
    page.goto(auto_memo_app.frontend_url)
    expect(page.locator("#shared-value")).to_have_text("/")

    page.locator("#to-other").click()
    expect(page.locator("#shared-value")).to_have_text("/other")
