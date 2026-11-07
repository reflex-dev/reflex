"""Test shared state imports from a reusable module."""

from collections.abc import Generator
from uuid import uuid4

import pytest
from playwright.sync_api import Page, expect

from reflex.state import RegistrationContext, reload_state_module
from reflex.testing import AppHarness
from reflex.utils.prerequisites import get_redis_sync
from reflex.utils.token_manager import RedisTokenManager


def SharedStateApp():
    """Create an app using a state class from a reusable module."""
    import reflex as rx
    from tests.integration.shared.state import SharedState

    class State(SharedState):
        pass

    def index() -> rx.Component:
        return rx.vstack(rx.text("Shared state loaded", id="shared-state"))

    app = rx.App()
    app.add_page(index)


@pytest.fixture
def shared_state(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start the app that imports a shared state class.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("shared_state"),
        app_source=SharedStateApp,
    ) as harness:
        yield harness


def test_shared_state(shared_state: AppHarness, page: Page) -> None:
    """The app can import a state class from a reusable module.

    Args:
        shared_state: harness for the shared state app.
        page: Playwright page.
    """
    assert shared_state.app_instance is not None, "app is not running"
    assert shared_state.frontend_url is not None
    page.goto(shared_state.frontend_url)
    expect(page.locator("#shared-state")).to_have_text("Shared state loaded")


def test_shared_module_state_is_available_to_a_second_app(
    tmp_path, monkeypatch, page: Page
) -> None:
    """A module first imported by one app remains usable by the next app."""
    import sys

    package_name = f"harness_shared_{uuid4().hex}"
    package_path = tmp_path / package_name
    package_path.mkdir()
    (package_path / "__init__.py").write_text("", encoding="utf-8")
    (package_path / "state.py").write_text(
        "import reflex as rx\n"
        "class SharedState(rx.State):\n"
        "    count: int = 0\n"
        "    @rx.event\n"
        "    def increment(self):\n"
        "        self.count += 1\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    assert f"{package_name}.state" not in sys.modules

    app_source = f"""
import reflex as rx
from {package_name}.state import SharedState

def index():
    return rx.vstack(
        rx.text(SharedState.count, id="shared-count"),
        rx.button("Increment", on_click=SharedState.increment, id="increment"),
    )

app = rx.App()
app.add_page(index)
"""
    base_context = RegistrationContext.ensure_context().fork()
    monkeypatch.setattr(AppHarness, "_base_registration_context", base_context)
    shared_module_name = f"{package_name}.state"

    try:
        for app_name in ("shared_state_first", "shared_state_second"):
            with AppHarness.create(
                root=tmp_path / app_name,
                app_name=app_name,
                app_source=app_source,
            ) as harness:
                assert harness.frontend_url is not None
                page.goto(harness.frontend_url)
                count = page.locator("#shared-count")
                expect(count).to_have_text("0")
                page.locator("#increment").click()
                expect(count).to_have_text("1")
                token = page.evaluate("() => sessionStorage.getItem('token')")
                assert token is not None
                token_manager = harness.token_manager()
                page.goto("about:blank")
                assert harness._poll_for(
                    lambda token=token, token_manager=token_manager: (
                        token not in token_manager.token_to_sid
                    )
                )
                if isinstance(token_manager, RedisTokenManager):
                    redis = get_redis_sync()
                    assert redis is not None
                    assert harness._poll_for(
                        lambda redis=redis, token=token, token_manager=token_manager: (
                            not redis.exists(token_manager._get_redis_key(token))
                        )
                    )
                    redis.close()
    finally:
        token = RegistrationContext.set(base_context)
        try:
            reload_state_module(shared_module_name)
        finally:
            RegistrationContext.reset(token)
