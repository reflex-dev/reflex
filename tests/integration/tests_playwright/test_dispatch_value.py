"""Integration test for speculative frontend updates with ``Var.dispatch_value``."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def DispatchValueApp():
    """App showing values on the frontend before the backend sends them."""
    import asyncio

    import reflex as rx

    class State(rx.State):
        status: rx.Field[str] = rx.field("idle")
        items: rx.Field[list[str]] = rx.field(default_factory=list)

        @rx.event
        async def work(self):
            await asyncio.sleep(1)
            self.status = "done"

    class Child(State):
        pass

    @rx.page("/")
    def index():
        return rx.box(
            rx.input(
                value=State.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.button(
                "Work",
                on_click=[State.status.dispatch_value("working"), State.work],
                id="work",
            ),
            rx.button(
                "Add",
                # An inherited var, dispatched to the state declaring it.
                on_click=Child.items.dispatch_value(["pending"]),
                id="add",
            ),
            rx.button(
                "Late",
                # Dispatched in turn, after the script before it.
                on_click=[
                    rx.call_script("void 0"),
                    State.status.dispatch_value("late"),
                    State.work,
                ],
                id="late",
            ),
            rx.text(State.status, id="status"),
            rx.text(State.items.join(","), id="items"),
        )

    app = rx.App()  # noqa: F841


@pytest.fixture(scope="module")
def dispatch_value_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start DispatchValueApp via AppHarness.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("dispatch_value_app"),
        app_source=DispatchValueApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_dispatch_value(dispatch_value_app: AppHarness, page: Page):
    """A dispatched value shows right away, until the backend sends the var.

    Args:
        dispatch_value_app: AppHarness running the test app.
        page: Playwright page.
    """
    assert dispatch_value_app.frontend_url is not None
    page.goto(dispatch_value_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    status = page.locator("#status")
    expect(status).to_have_text("idle")
    page.click("#work")
    # The backend never sets "working": only the frontend shows it.
    expect(status).to_have_text("working")
    expect(status).to_have_text("done")

    page.click("#add")
    expect(page.locator("#items")).to_have_text("pending")


def test_dispatch_value_before_connecting(dispatch_value_app: AppHarness, page: Page):
    """A dispatched value leading its events shows while the backend is unreachable.

    Args:
        dispatch_value_app: AppHarness running the test app.
        page: Playwright page.
    """
    assert dispatch_value_app.frontend_url is not None
    # Hold the websocket without ever reaching the backend.
    page.route_web_socket("**/_event/**", lambda ws: None)
    page.goto(dispatch_value_app.frontend_url)

    status = page.locator("#status")
    expect(status).to_have_text("idle")
    page.click("#work")
    expect(status).to_have_text("working")

    # Events before a dispatched value run first: here they wait for the backend.
    page.click("#late")
    page.wait_for_timeout(500)
    expect(status).to_have_text("working")
