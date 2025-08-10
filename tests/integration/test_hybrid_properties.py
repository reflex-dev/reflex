"""Test hybrid properties."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from reflex.testing import DEFAULT_TIMEOUT, AppHarness, WebDriver


def HybridProperties():
    """Test app for hybrid properties."""
    import reflex as rx
    from reflex.experimental import hybrid_property
    from reflex.vars import Var

    class State(rx.State):
        first_name: str = "John"
        last_name: str = "Doe"

        @property
        def python_full_name(self) -> str:
            """A normal python property to showcase the current behavior. This renders to smth like `<property object at 0x723b334e5940>`.

            Returns:
                str: The full name of the person.
            """
            return f"{self.first_name} {self.last_name}"

        @hybrid_property
        def full_name(self) -> str:
            """A simple hybrid property which uses the same code for both frontend and backend.

            Returns:
                str: The full name of the person.
            """
            return f"{self.first_name} {self.last_name}"

        @hybrid_property
        def has_last_name(self) -> str:
            """A more complex hybrid property which uses different code for frontend and backend.

            Returns:
                str: "yes" if the person has a last name, "no" otherwise.
            """
            return "yes" if self.last_name else "no"

        @has_last_name.var
        def has_last_name(cls) -> Var[str]:
            """The frontend code for the `has_last_name` hybrid property.

            Returns:
                Var[str]: The value of the hybrid property.
            """
            return rx.cond(cls.last_name, "yes", "no")

    def index() -> rx.Component:
        return rx.center(
            rx.vstack(
                rx.input(
                    id="token",
                    value=State.router.session.client_token,
                    is_read_only=True,
                ),
                rx.text(
                    f"python_full_name: {State.python_full_name}", id="python_full_name"
                ),
                rx.text(f"full_name: {State.full_name}", id="full_name"),
                rx.text(f"has_last_name: {State.has_last_name}", id="has_last_name"),
                rx.input(
                    value=State.last_name,
                    on_change=State.setvar("last_name"),
                    id="set_last_name",
                ),
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def hybrid_properties(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start HybridProperties app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("hybrid_properties"),
        app_source=HybridProperties,
    ) as harness:
        yield harness


@pytest.fixture
def driver(hybrid_properties: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the hybrid_properties app.

    Args:
        hybrid_properties: harness for HybridProperties app

    Yields:
        WebDriver instance.
    """
    assert hybrid_properties.app_instance is not None, "app is not running"
    driver = hybrid_properties.frontend()
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture
def token(hybrid_properties: AppHarness, driver: WebDriver) -> str:
    """Get a function that returns the active token.

    Args:
        hybrid_properties: harness for HybridProperties app.
        driver: WebDriver instance.

    Returns:
        The token for the connected client
    """
    assert hybrid_properties.app_instance is not None
    token_input = driver.find_element(By.ID, "token")
    assert token_input

    # wait for the backend connection to send the token
    token = hybrid_properties.poll_for_value(token_input, timeout=DEFAULT_TIMEOUT * 2)
    assert token is not None

    return token


@pytest.mark.asyncio
async def test_hybrid_properties(
    hybrid_properties: AppHarness,
    driver: WebDriver,
    token: str,
):
    """Test that hybrid properties are working as expected.

    Args:
        hybrid_properties: harness for HybridProperties app.
        driver: WebDriver instance.
        token: The token for the connected client.
    """
    assert hybrid_properties.app_instance is not None

    state_name = hybrid_properties.get_state_name("_state")
    full_state_name = hybrid_properties.get_full_state_name(["_state"])
    token = f"{token}_{full_state_name}"

    state = (await hybrid_properties.get_state(token)).substates[state_name]
    assert state is not None
    assert state.full_name == "John Doe"
    assert state.has_last_name == "yes"

    full_name = driver.find_element(By.ID, "full_name")
    assert full_name.text == "full_name: John Doe"

    python_full_name = driver.find_element(By.ID, "python_full_name")
    assert "<property object at 0x" in python_full_name.text

    has_last_name = driver.find_element(By.ID, "has_last_name")
    assert has_last_name.text == "has_last_name: yes"

    set_last_name = driver.find_element(By.ID, "set_last_name")
    # clear the input
    set_last_name.send_keys(Keys.CONTROL + "a")
    set_last_name.send_keys(Keys.DELETE)

    assert (
        hybrid_properties.poll_for_content(
            has_last_name, exp_not_equal="has_last_name: yes"
        )
        == "has_last_name: no"
    )

    assert full_name.text == "full_name: John"

    state = (await hybrid_properties.get_state(token)).substates[state_name]
    assert state is not None
    assert state.full_name == "John "
    assert state.has_last_name == "no"
