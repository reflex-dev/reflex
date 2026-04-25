"""Integration tests for in-memory state expiration."""

import time
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.istate.manager.memory import StateManagerMemory
from reflex.testing import AppHarness

from . import utils


def MemoryExpirationApp():
    """Reflex app that exposes state expiration through a simple counter UI."""
    import reflex as rx

    class State(rx.State):
        counter: int = 0

        @rx.event
        def increment(self):
            self.counter += 1

    app = rx.App()

    @app.add_page
    def index():
        return rx.vstack(
            rx.input(
                id="token",
                value=State.router.session.client_token,
                is_read_only=True,
            ),
            rx.text(State.counter, id="counter"),
            rx.button("Increment", id="increment", on_click=State.increment),
        )


@pytest.fixture(scope="module")
def memory_expiration_app(
    app_harness_env: type[AppHarness],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start a memory-backed app with a short expiration window.

    Yields:
        A running app harness configured to use StateManagerMemory.
    """
    monkeypatch.setenv("REFLEX_STATE_MANAGER_MODE", "memory")
    # Memory expiration reuses the shared token_expiration config field.
    monkeypatch.setenv("REFLEX_REDIS_TOKEN_EXPIRATION", "1")

    with app_harness_env.create(
        root=tmp_path_factory.mktemp("memory_expiration_app"),
        app_name=f"memory_expiration_{app_harness_env.__name__.lower()}",
        app_source=MemoryExpirationApp,
    ) as harness:
        assert isinstance(
            getattr(harness.app_instance, "state_manager", None), StateManagerMemory
        )
        yield harness


def test_memory_state_manager_expires_state_end_to_end(
    memory_expiration_app: AppHarness,
    page: Page,
):
    """An idle in-memory state should expire and reset on the next event."""
    app_instance = memory_expiration_app.app_instance
    assert app_instance is not None
    assert memory_expiration_app.frontend_url is not None
    page.goto(memory_expiration_app.frontend_url)

    token = utils.poll_for_token(page)
    assert token is not None

    token_input = page.locator("#token")
    counter = page.locator("#counter")
    increment = page.locator("#increment")
    app_state_manager = app_instance.state_manager
    assert isinstance(app_state_manager, StateManagerMemory)

    expect(counter).to_have_text("0")

    increment.click()
    expect(counter).to_have_text("1")

    increment.click()
    expect(counter).to_have_text("2")

    AppHarness.expect(lambda: token in app_state_manager.states)
    AppHarness.expect(lambda: token not in app_state_manager.states, timeout=5)

    increment.click()
    expect(counter).to_have_text("1")
    assert token_input.input_value() == token


def test_memory_state_manager_delays_expiration_after_use_end_to_end(
    memory_expiration_app: AppHarness,
    page: Page,
):
    """Using a token should start a fresh expiration window from the last use."""
    app_instance = memory_expiration_app.app_instance
    assert app_instance is not None
    assert memory_expiration_app.frontend_url is not None
    page.goto(memory_expiration_app.frontend_url)

    token = utils.poll_for_token(page)
    assert token is not None

    token_input = page.locator("#token")
    counter = page.locator("#counter")
    increment = page.locator("#increment")
    app_state_manager = app_instance.state_manager
    assert isinstance(app_state_manager, StateManagerMemory)

    expect(counter).to_have_text("0")

    increment.click()
    expect(counter).to_have_text("1")
    AppHarness.expect(lambda: token in app_state_manager.states)

    time.sleep(0.6)
    increment.click()
    expect(counter).to_have_text("2")
    AppHarness.expect(lambda: token in app_state_manager.states)

    time.sleep(0.6)
    increment.click()
    expect(counter).to_have_text("3")
    AppHarness.expect(lambda: token in app_state_manager.states)

    time.sleep(0.6)
    assert token in app_state_manager.states
    assert counter.text_content() == "3"

    AppHarness.expect(lambda: token not in app_state_manager.states, timeout=5)

    increment.click()
    expect(counter).to_have_text("1")
    assert token_input.input_value() == token
