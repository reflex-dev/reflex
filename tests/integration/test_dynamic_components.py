"""Integration tests for var operations."""

from collections.abc import Generator
from typing import TypeVar

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness

# pyright: reportOptionalMemberAccess=false, reportGeneralTypeIssues=false, reportUnknownMemberType=false


def DynamicComponents():
    """App with var operations."""
    import reflex as rx

    class DynamicComponentsState(rx.State):
        value: int = 10
        count: int = 0
        late_component: rx.Component = rx.el.div("Waiting", id="late-component")

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
        def show_card(self):
            """Introduce a Radix export that is absent from the initial page."""
            self.late_component = rx.card(
                rx.el.button(
                    "Count from card",
                    id="late-increment",
                    on_click=DynamicComponentsState.set_count(self.count + 1),
                ),
                id="late-card",
            )

        @rx.event
        def set_count(self, count: int):
            """Set the counter value.

            Args:
                count: The new counter value.
            """
            self.count = count

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
            DynamicComponentsState.late_component,
            rx.el.button(
                "Show card",
                id="show-card",
                on_click=DynamicComponentsState.show_card,
            ),
            rx.text(
                DynamicComponentsState._evaluate(
                    lambda state: factorial(state.value), of_type=int
                ),
                id="factorial",
            ),
        )


@pytest.fixture(scope="module")
def dynamic_components(
    app_harness_env: type[AppHarness], tmp_path_factory
) -> Generator[AppHarness, None, None]:
    """Start VarOperations app at tmp_path via AppHarness.

    Args:
        app_harness_env: Development or production harness class.
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with app_harness_env.create(
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
        AppHarness.poll_for_or_raise_timeout(
            lambda: driver.find_element(By.ID, "token")
        )
        # The test verifies backend readiness through the button/counter events.
        yield driver
    finally:
        driver.quit()


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

    driver.find_element(By.ID, "show-card").click()
    late_button = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "late-increment")
    )
    late_button.click()
    assert AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "count").text == "1"
    )
