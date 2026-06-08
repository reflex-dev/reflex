"""Integration test for resilience against deltas referencing unknown states.

Regression coverage for https://github.com/reflex-dev/reflex/issues/6616 where a
``ComponentState`` whose dynamically-generated name desynced between the compiled
frontend and the backend caused ``TypeError: d is not a function`` (an unhandled
rejection inside the socket ``event`` handler) which broke the whole event loop.

The frontend must ignore a delta entry whose substate has no reducer instead of
crashing, and must keep processing events afterwards.
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def UnknownSubstateApp():
    """App that emits a delta referencing a substate the frontend cannot dispatch."""
    import reflex as rx
    from reflex.state import StateUpdate

    # A substate name the compiled frontend has no dispatcher for, mimicking an
    # orphaned dynamic ComponentState (e.g. ``..._n2``) only the backend knows.
    UNKNOWN_SUBSTATE = "reflex___state____state.this_substate_does_not_exist"

    class State(rx.State):
        clicks: int = 0

        @rx.event
        async def do_apply(self):
            # A normal var update, proving the event loop keeps working.
            self.clicks += 1
            # Out-of-band delta carrying a substate with no frontend reducer.
            await app.event_namespace.emit_update(
                update=StateUpdate(delta={UNKNOWN_SUBSTATE: {"x_rx_state_": 1}}),
                token=self.router.session.client_token,
            )

    @rx.page("/")
    def index():
        return rx.box(
            rx.input(
                value=State.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.button("apply", on_click=State.do_apply, id="apply"),
            rx.text(State.clicks.to_string(), id="clicks"),
        )

    app = rx.App()


@pytest.fixture(scope="module")
def unknown_substate_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start UnknownSubstateApp via AppHarness.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("unknown_substate_app"),
        app_source=UnknownSubstateApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_unknown_substate_delta_does_not_crash(
    unknown_substate_app: AppHarness, page: Page
):
    """A delta with an unknown substate is ignored without breaking the app.

    Args:
        unknown_substate_app: AppHarness running the test app.
        page: Playwright page.
    """
    assert unknown_substate_app.frontend_url is not None

    page_errors: list[str] = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    # The original crash surfaced as an unhandled promise rejection (the socket
    # ``event`` handler is async), which does not trigger ``pageerror``.
    page.add_init_script(
        "window.__rejections = [];"
        "window.addEventListener('unhandledrejection',"
        " (e) => window.__rejections.push("
        "String(e.reason && (e.reason.message || e.reason))));"
    )

    page.goto(unknown_substate_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    # Triggers both the normal `clicks` delta and the unknown-substate delta.
    page.locator("#apply").click()
    # The normal update still lands, so the event loop survived the unknown delta.
    expect(page.locator("#clicks")).to_have_text("1")

    rejections = page.evaluate("window.__rejections")
    assert not rejections, f"Unhandled rejections in frontend: {rejections}"
    assert not page_errors, f"Frontend raised unexpected errors: {page_errors}"
