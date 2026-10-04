"""Integration tests for reporting state deltas the frontend cannot process.

A delta whose substate has no dispatch function in the compiled frontend means
the frontend and backend disagree about the state tree. The frontend reports it
back over the ``client_error`` socket event so the failure is visible in the
backend logs instead of being dropped silently. Known substates and subsequent
events continue to work without requiring a reload.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.state import StateUpdate
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
        mixed_delta: int = 0
        callback_count: int = 0

        @rx.event
        def callback(self):
            """Count events returned with a mixed delta."""
            self.callback_count += 1

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

        @rx.event
        async def send_mixed_delta(self):
            """Emit known and unknown substates with a follow-up event."""
            self.mixed_delta += 1
            assert app.event_namespace is not None
            await app.event_namespace.emit_update(
                StateUpdate(
                    delta={
                        ghost_substate: {"value": 1},
                        self.get_full_name(): {"mixed_delta": self.mixed_delta},
                    },
                    events=rx.event.Event.from_event_type(ClientErrorState.callback),
                ),
                self.router.session.client_token,
            )

    @rx.page("/")
    def index():
        return rx.box(
            rx.text(ClientErrorState.counter, id="counter"),
            rx.text(ClientErrorState.mixed_delta, id="mixed-delta"),
            rx.text(ClientErrorState.callback_count, id="callback-count"),
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
            rx.button(
                "mixed",
                on_click=ClientErrorState.send_mixed_delta,
                id="mixed-btn",
            ),
        )

    app = rx.App()


@pytest.fixture(scope="module")
def client_error_app(
    tmp_path_factory: pytest.TempPathFactory,
    app_harness_env: type[AppHarness],
) -> Generator[AppHarness, None, None]:
    """Start the ClientErrorApp.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.
        app_harness_env: Development or production app harness.

    Yields:
        Running AppHarness instance.
    """
    with app_harness_env.create(
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


@pytest.mark.parametrize("trigger", ["#break-btn", "#mixed-btn"])
def test_unknown_substate_does_not_stop_events(
    client_error_app: AppHarness,
    page: Page,
    monkeypatch: pytest.MonkeyPatch,
    trigger: str,
):
    """Skip unknown substates while preserving updates and subsequent events.

    Args:
        client_error_app: Running AppHarness instance.
        page: Playwright page fixture.
        monkeypatch: pytest fixture for patching the exception handler.
        trigger: Button that emits an unknown-only or mixed delta.
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

    token = page.locator("#token").input_value()
    page.click(trigger)
    assert AppHarness._poll_for(lambda: reports), (
        "backend was not told about the unprocessable delta"
    )

    # No automatic reload: the page's original navigation entry is still live.
    assert (
        page.evaluate("() => performance.getEntriesByType('navigation')[0].type")
        == "navigate"
    )

    if trigger == "#mixed-btn":
        expect(page.locator("#mixed-delta")).to_have_text("1")
        expect(page.locator("#callback-count")).to_have_text("1")

    # Repeated unknown substates are skipped without repeating the report.
    page.click(trigger)
    page.click("#bump-btn")
    expect(page.locator("#counter")).to_have_text("1")
    if trigger == "#mixed-btn":
        expect(page.locator("#mixed-delta")).to_have_text("2")
        expect(page.locator("#callback-count")).to_have_text("2")
    expect(page.locator("#token")).to_have_value(token)
    assert len(reports) == 1


def test_unknown_substate_during_hydration(
    client_error_app: AppHarness, page: Page, monkeypatch: pytest.MonkeyPatch
):
    """Hydrate known state even when every update includes an unknown substate.

    Args:
        client_error_app: Running AppHarness instance.
        page: Playwright page fixture.
        monkeypatch: pytest fixture for patching outgoing updates.
    """
    assert client_error_app.frontend_url is not None
    assert client_error_app.app_instance is not None
    namespace = client_error_app.app_instance.event_namespace
    assert namespace is not None
    emit_update = namespace.emit_update
    reports: list[str] = []
    monkeypatch.setattr(
        client_error_app.app_instance,
        "frontend_exception_handler",
        lambda exc: reports.append(str(exc)),
    )

    async def emit_with_unknown_substate(update: StateUpdate, token: str) -> None:
        """Simulate a backend whose state tree exceeds the frontend bundle.

        Args:
            update: Outgoing state update.
            token: Client receiving the update.
        """
        await emit_update(
            dataclasses.replace(
                update, delta={**update.delta, GHOST_SUBSTATE: {"value": 1}}
            ),
            token,
        )

    monkeypatch.setattr(namespace, "emit_update", emit_with_unknown_substate)
    page.goto(client_error_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    page.click("#bump-btn")
    expect(page.locator("#counter")).to_have_text("1")
    assert AppHarness._poll_for(lambda: reports)
    assert len(reports) == 1
    assert GHOST_SUBSTATE in reports[0]
