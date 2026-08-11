"""Integration tests for reporting state deltas the frontend cannot process.

A delta whose substate has no dispatch function in the compiled frontend means
the frontend and backend disagree about the state tree. The frontend reports it
back over the ``client_error`` socket event so the failure is visible in the
backend logs instead of being dropped silently, then stops sending events —
the mismatch is fatal until the developer rebuilds the frontend or fixes
``api_url``.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

# Substate name with no dispatch function in the compiled frontend.
GHOST_SUBSTATE = "reflex___state____state____ghost_state"


def ClientErrorApp():
    """App that can emit a state delta the frontend cannot process."""
    import reflex as rx
    from reflex.state import StateUpdate

    ghost_substate = "reflex___state____state____ghost_state"

    class ClientErrorState(rx.State):
        counter: int = 0

        @rx.event
        def bump(self):
            self.counter += 1

        @rx.event
        async def send_unprocessable_delta(self):
            assert app.event_namespace is not None
            await app.event_namespace.emit_update(
                StateUpdate(delta={ghost_substate: {"value": 1}}),
                self.router.session.client_token,
            )

    @rx.page("/")
    def index():
        return rx.box(
            rx.text(ClientErrorState.counter, id="counter"),
            rx.input(
                value=ClientErrorState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.button("bump", on_click=ClientErrorState.bump, id="bump-btn"),
            rx.button(
                "break",
                on_click=ClientErrorState.send_unprocessable_delta,
                id="break-btn",
            ),
        )

    app = rx.App()


@pytest.fixture(scope="module")
def client_error_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start the ClientErrorApp.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("client_error_app"),
        app_source=ClientErrorApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_unprocessable_delta_is_reported_to_backend(
    client_error_app: AppHarness, page: Page, monkeypatch: pytest.MonkeyPatch
):
    """An unprocessable delta reaches the backend's frontend exception handler.

    Args:
        client_error_app: Running AppHarness instance.
        page: Playwright page fixture.
        monkeypatch: pytest fixture for patching the exception handler.
    """
    assert client_error_app.frontend_url is not None
    assert client_error_app.app_instance is not None
    page.goto(client_error_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    # The socket works before the mismatch.
    page.click("#bump-btn")
    expect(page.locator("#counter")).to_have_text("1")

    reports: list[str] = []
    monkeypatch.setattr(
        client_error_app.app_instance,
        "frontend_exception_handler",
        lambda exc: reports.append(str(exc)),
    )

    page.click("#break-btn")

    assert AppHarness._poll_for(lambda: reports), (
        "backend was not told about the unprocessable delta"
    )
    report = reports[0]
    assert GHOST_SUBSTATE in report
    assert "no dispatch function" in report
    assert "rebuild" in report.lower()


def test_unprocessable_delta_is_fatal_without_reload(
    client_error_app: AppHarness, page: Page, monkeypatch: pytest.MonkeyPatch
):
    """A mismatch is reported exactly once and does not reload the page.

    Recovery (rebuild or api_url fix) is the developer's decision, so the
    frontend must not reload on its own or keep re-reporting.

    Args:
        client_error_app: Running AppHarness instance.
        page: Playwright page fixture.
        monkeypatch: pytest fixture for patching the exception handler.
    """
    assert client_error_app.frontend_url is not None
    assert client_error_app.app_instance is not None
    page.goto(client_error_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    reports: list[str] = []
    monkeypatch.setattr(
        client_error_app.app_instance,
        "frontend_exception_handler",
        lambda exc: reports.append(str(exc)),
    )

    page.click("#break-btn")
    assert AppHarness._poll_for(lambda: reports), (
        "backend was not told about the unprocessable delta"
    )

    # No automatic reload: the page's original navigation entry is still live.
    assert (
        page.evaluate("() => performance.getEntriesByType('navigation')[0].type")
        == "navigate"
    )

    # The mismatch is fatal: further clicks send no events and add no reports.
    page.click("#break-btn")
    page.click("#bump-btn")
    page.wait_for_timeout(500)
    expect(page.locator("#counter")).to_have_text("0")
    assert len(reports) == 1
