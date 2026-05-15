"""Integration tests for ``rx.memo`` runtime behavior.

Covers behaviors previously exercised by the deleted
``tests/integration/test_memo.py`` (Selenium): partial-application of an
``EventHandler`` prop (``event(some_value)``) and raw pass-through to an
inner event trigger (``on_change=event``).
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def MemoApp():
    """App exercising ``rx.memo`` with ``EventHandler`` props."""
    import reflex as rx

    class MemoState(rx.State):
        last_value: str = ""

        @rx.event
        def set_last_value(self, value: str):
            self.last_value = value

    @rx.memo
    def my_memoed_component(
        some_value: rx.Var[str],
        event: rx.EventHandler[rx.event.passthrough_event_spec(str)],
    ) -> rx.Component:
        return rx.vstack(
            rx.button(some_value, id="memo-button", on_click=event(some_value)),
            rx.input(id="memo-input", on_change=event),
        )

    def index() -> rx.Component:
        return rx.vstack(
            rx.text(MemoState.last_value, id="memo-last-value"),
            my_memoed_component(
                some_value="memod_some_value", event=MemoState.set_last_value
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def memo_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Run the memo app under an AppHarness.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        The running harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("memo_app"),
        app_source=MemoApp,
    ) as harness:
        yield harness


def test_memo_event_handler_partial_application(
    memo_app: AppHarness, page: Page
) -> None:
    """Clicking a button whose ``on_click`` is ``event(some_value)`` dispatches it.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)

    expect(page.locator("#memo-last-value")).to_have_text("")
    page.click("#memo-button")
    expect(page.locator("#memo-last-value")).to_have_text("memod_some_value")


def test_memo_event_handler_raw_pass_through(memo_app: AppHarness, page: Page) -> None:
    """Typing into an input whose ``on_change`` is the raw handler dispatches it.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)

    page.locator("#memo-input").fill("typed_value")
    expect(page.locator("#memo-last-value")).to_have_text("typed_value")
