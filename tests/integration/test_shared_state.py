"""Test shared state."""

from __future__ import annotations

from collections.abc import Generator
from uuid import uuid4

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from reflex.testing import AppHarness, WebDriver


def SharedStateApp():
    """Test that shared state works as expected."""
    import reflex as rx
    from tests.integration.shared.state import SharedState

    class State(SharedState):
        pass

    def index() -> rx.Component:
        return rx.vstack()

    app = rx.App()
    app.add_page(index)


@pytest.fixture
def shared_state(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start SharedStateApp at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance

    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("shared_state"),
        app_source=SharedStateApp,
    ) as harness:
        yield harness


@pytest.fixture
def driver(shared_state: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the shared_state app.

    Args:
        shared_state: harness for SharedStateApp

    Yields:
        WebDriver instance.

    """
    assert shared_state.app_instance is not None, "app is not running"
    driver = shared_state.frontend()
    try:
        yield driver
    finally:
        driver.quit()


def test_shared_state(
    shared_state: AppHarness,
    driver: WebDriver,
):
    """Test that 2 AppHarness instances can share a state (f.e. from a library).

    Args:
        shared_state: harness for SharedStateApp.
        driver: WebDriver instance.

    """
    assert shared_state.app_instance is not None


def test_shared_module_state_is_available_to_a_second_app(tmp_path, monkeypatch):
    """A module first imported by one app remains usable by the next app."""
    import sys

    from reflex.state import reload_state_module

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

    try:
        for app_name in ("shared_state_first", "shared_state_second"):
            with AppHarness.create(
                root=tmp_path / app_name,
                app_name=app_name,
                app_source=app_source,
            ) as harness:
                driver = harness.frontend()
                try:
                    count = WebDriverWait(driver, 15).until(
                        lambda current: current.find_element(By.ID, "shared-count")
                    )
                    assert count.text == "0"
                    driver.find_element(By.ID, "increment").click()
                    WebDriverWait(driver, 10).until(lambda _: count.text == "1")
                finally:
                    driver.quit()
    finally:
        reload_state_module(f"{package_name}.state")
