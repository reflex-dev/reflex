"""Integration tests for compiler-generated experimental memos."""

from collections.abc import Generator

import pytest
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
