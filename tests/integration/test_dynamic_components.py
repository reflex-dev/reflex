"""Integration tests for var operations."""

import os
import sys
from collections.abc import Generator
from typing import TypeVar

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness

# pyright: reportOptionalMemberAccess=false, reportGeneralTypeIssues=false, reportUnknownMemberType=false


def DynamicComponents():
    """App with var operations."""
    import reflex as rx
    from reflex.components.dynamic import bundle_library

    bundle_library(rx.text())
    bundle_library(rx.hstack(rx.el.div(rx.icon("banana"))))

    class DynamicComponentsState(rx.State):
        value: int = 10
        count: int = 0
        icon_name: str = "apple"
        activated: bool = False

        button: rx.Component = rx.button(
            "Click me",
            custom_attrs={
                "id": "button",
            },
        )

        @rx.event
        def got_clicked(self):
            self.button = rx.button(
                "Clicked",
                custom_attrs={
                    "id": "button",
                },
            )

        @rx.event
        def set_count(self, count: int):
            """Set the counter value.

            Args:
                count: The new counter value.
            """
            self.count = count

        @rx.event
        def toggle_activated(self):
            """Show or hide a component absent from the initial state."""
            self.activated = not self.activated

        @rx.var
        def client_token_component(self) -> rx.Component:
            return rx.vstack(
                rx.el.input(
                    custom_attrs={
                        "id": "token",
                    },
                    value=self.router.session.client_token,
                    is_read_only=True,
                ),
                rx.button(
                    "Update",
                    custom_attrs={
                        "id": "update",
                    },
                    on_click=DynamicComponentsState.got_clicked,
                ),
            )

        @rx.var
        def counter_component(self) -> rx.Component:
            """Get a dynamic counter component with event handlers.

            Returns:
                The dynamic counter component.
            """
            return rx.hstack(
                rx.button(
                    "-",
                    id="decrement",
                    on_click=DynamicComponentsState.set_count(self.count - 1),
                ),
                rx.text(self.count, id="count"),
                rx.button(
                    "+",
                    id="increment",
                    on_click=DynamicComponentsState.set_count(self.count + 1),
                ),
            )

        @rx.var
        def icon_component(self) -> rx.Component:
            """Get icons with default and named bundled subpath imports.

            Returns:
                Static and reactive Lucide icons rendered dynamically.
            """
            return rx.hstack(
                rx.icon("apple", id="dynamic-icon"),
                rx.icon(DynamicComponentsState.icon_name, id="dynamic-named-icon"),
            )

        @rx.var
        def delayed_counter(self) -> rx.Component:
            """Render an explicitly bundled icon only after activation.

            Returns:
                A delayed counter with working event handlers, or an initial icon.
            """
            if not self.activated:
                return rx.icon("tag", color="red", id="initial-icon")
            return rx.hstack(
                rx.icon("banana", color="green", id="delayed-icon"),
                rx.button(
                    "-",
                    id="delayed-decrement",
                    on_click=DynamicComponentsState.set_count(self.count - 1),
                ),
                rx.text(self.count, id="delayed-count"),
                rx.button(
                    "+",
                    id="delayed-increment",
                    on_click=DynamicComponentsState.set_count(self.count + 1),
                ),
            )

    app = rx.App()

    def factorial(n: int) -> int:
        if n == 0:
            return 1
        return n * factorial(n - 1)

    @app.add_page
    def index():
        return rx.vstack(
            DynamicComponentsState.client_token_component,
            DynamicComponentsState.button,
            DynamicComponentsState.counter_component,
            DynamicComponentsState.icon_component,
            rx.button(
                "Activate",
                id="activate",
                on_click=DynamicComponentsState.toggle_activated,
            ),
            DynamicComponentsState.delayed_counter,
            rx.text(
                DynamicComponentsState._evaluate(
                    lambda state: factorial(state.value), of_type=int
                ),
                id="factorial",
            ),
        )


@pytest.fixture(scope="module")
def dynamic_components(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start VarOperations app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("dynamic_components"),
        app_source=DynamicComponents,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


T = TypeVar("T")


@pytest.fixture
def driver(dynamic_components: AppHarness):
    """Get an instance of the browser open to the dynamic components app.

    Args:
        dynamic_components: AppHarness for the dynamic components

    Yields:
        WebDriver instance.
    """
    driver = dynamic_components.frontend()
    try:
        token_input = AppHarness.poll_for_or_raise_timeout(
            lambda: driver.find_element(By.ID, "token")
        )
        # wait for the backend connection to send the token
        token = dynamic_components.poll_for_value(token_input)
        assert token is not None

        yield driver
    finally:
        driver.quit()


# TODO: drop the skip once the dill release fixing
# https://github.com/uqfoundation/dill/issues/753 lands in uv.lock
@pytest.mark.skipif(
    sys.version_info >= (3, 15) and bool(os.environ.get("REFLEX_REDIS_URL")),
    reason="dill <= 0.4.1 cannot serialize functions on Python 3.15",
)
def test_dynamic_components(driver, dynamic_components: AppHarness):
    """Test that the var operations produce the right results.

    Args:
        driver: selenium WebDriver open to the app
        dynamic_components: AppHarness for the dynamic components
    """
    button = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "button")
    )
    assert button.text == "Click me"

    update_button = driver.find_element(By.ID, "update")
    assert update_button
    update_button.click()

    assert AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "button").text == "Clicked"
    )

    factorial = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "factorial")
    )
    assert factorial.text == "3628800"

    for icon_id in ("dynamic-icon", "dynamic-named-icon"):
        AppHarness.poll_for_or_raise_timeout(
            lambda icon_id=icon_id: driver.find_element(By.ID, icon_id)
        )

    count = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "count")
    )
    assert count.text == "0"

    increment = driver.find_element(By.ID, "increment")
    increment.click()
    assert AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "count").text == "1"
    )

    decrement = driver.find_element(By.ID, "decrement")
    decrement.click()
    assert AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "count").text == "0"
    )

    assert not driver.find_elements(By.ID, "delayed-icon")
    assert driver.find_element(By.ID, "initial-icon")
    driver.find_element(By.ID, "activate").click()
    AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "delayed-icon")
    )
    driver.find_element(By.ID, "delayed-increment").click()
    AppHarness.expect(lambda: driver.find_element(By.ID, "delayed-count").text == "1")
    driver.find_element(By.ID, "delayed-decrement").click()
    AppHarness.expect(lambda: driver.find_element(By.ID, "delayed-count").text == "0")
    driver.find_element(By.ID, "activate").click()
    AppHarness.expect(lambda: not driver.find_elements(By.ID, "delayed-icon"))
    AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "initial-icon")
    )
    driver.find_element(By.ID, "activate").click()
    AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "delayed-icon")
    )
