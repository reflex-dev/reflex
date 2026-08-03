"""Integration tests for stateful ``rx.cond`` and ``rx.match`` rendering."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def CondMatchApp():
    """App exercising conditional rendering across state transitions."""
    import reflex as rx

    class CondMatchState(rx.State):
        val_a: str = "A"
        val_b: str = "B"

        @rx.event
        def select_a(self):
            self.val_a = "A"

        @rx.event
        def select_b(self):
            self.val_a = "B"

        @rx.event
        def select_c(self):
            self.val_a = "C"

    def index():
        return rx.box(
            rx.hstack(
                rx.button("A", on_click=CondMatchState.select_a, id="select-a"),
                rx.button("B", on_click=CondMatchState.select_b, id="select-b"),
                rx.button("C", on_click=CondMatchState.select_c, id="select-c"),
            ),
            rx.text(CondMatchState.val_a, id="current-value"),
            rx.box(
                rx.cond(
                    CondMatchState.val_a == "A",
                    rx.text(CondMatchState.val_a, id="cond-true"),
                    rx.text(CondMatchState.val_b, id="cond-false"),
                ),
                id="cond-container",
            ),
            rx.box(
                rx.match(
                    CondMatchState.val_a,
                    ("A", rx.text(CondMatchState.val_a + " is selected", id="match-a")),
                    ("B", rx.text(CondMatchState.val_b + " is selected", id="match-b")),
                    rx.text("No value selected", id="match-default"),
                ),
                id="match-container",
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def cond_match_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Create a harness for the cond/match regression app.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness for the test app.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("cond_match_app"),
        app_source=CondMatchApp,
    ) as harness:
        yield harness


def test_cond_and_match_render_only_selected_branch(
    cond_match_app: AppHarness, page: Page
):
    """Cond and Match should render exactly one active branch per state value.

    Args:
        cond_match_app: Running harness for the cond/match app.
        page: Playwright page.
    """
    assert cond_match_app.frontend_url is not None
    page.goto(cond_match_app.frontend_url)

    expect(page.locator("#current-value")).to_have_text("A")
    expect(page.locator("#cond-true")).to_have_text("A")
    expect(page.locator("#cond-false")).to_have_count(0)
    expect(page.locator("#match-a")).to_have_text("A is selected")
    expect(page.locator("#match-b")).to_have_count(0)
    expect(page.locator("#match-default")).to_have_count(0)

    page.click("#select-b")
    expect(page.locator("#current-value")).to_have_text("B")
    expect(page.locator("#cond-true")).to_have_count(0)
    expect(page.locator("#cond-false")).to_have_text("B")
    expect(page.locator("#match-a")).to_have_count(0)
    expect(page.locator("#match-b")).to_have_text("B is selected")
    expect(page.locator("#match-default")).to_have_count(0)

    page.click("#select-c")
    expect(page.locator("#current-value")).to_have_text("C")
    expect(page.locator("#cond-true")).to_have_count(0)
    expect(page.locator("#cond-false")).to_have_text("B")
    expect(page.locator("#match-a")).to_have_count(0)
    expect(page.locator("#match-b")).to_have_count(0)
    expect(page.locator("#match-default")).to_have_text("No value selected")
