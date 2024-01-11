"""Test state inheritance."""

from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import DEFAULT_TIMEOUT, AppHarness, WebDriver


def StateInheritance():
    """Test that state inheritance works as expected."""
    import reflex as rx

    class ChildMixin:
        @rx.var
        def child_mixin(self) -> str:
            return "child_mixin"

    class Mixin(ChildMixin):
        @rx.var
        def mixin(self) -> str:
            return "mixin"

    class OtherMixin(rx.Base):
        @rx.var
        def other_mixin(self) -> str:
            return "other_mixin"

    class Base1(rx.State, Mixin):
        @rx.var
        def basevar(self) -> str:
            return "basevar1"

    class Base2(rx.State):
        @rx.var
        def basevar(self) -> str:
            return "basevar2"

    class Child1(Base1, OtherMixin):
        pass

    class Child2(Base2, Mixin, OtherMixin):
        pass

    class Child3(Child2):
        @rx.var
        def childvar(self) -> str:
            return "childvar"

    def index() -> rx.Component:
        return rx.vstack(
            rx.input(
                id="token", value=Base1.router.session.client_token, is_read_only=True
            ),
            rx.heading(Base1.mixin, id="base1-mixin"),
            rx.heading(Base1.basevar, id="base1-basevar"),
            rx.heading(Base1.child_mixin, id="base1-child-mixin"),
            rx.heading(Base2.basevar, id="base2-basevar"),
            rx.heading(Child1.basevar, id="child1-basevar"),
            rx.heading(Child1.mixin, id="child1-mixin"),
            rx.heading(Child1.other_mixin, id="child1-other-mixin"),
            rx.heading(Child1.child_mixin, id="child1-child-mixin"),
            rx.heading(Child2.basevar, id="child2-basevar"),
            rx.heading(Child2.mixin, id="child2-mixin"),
            rx.heading(Child2.other_mixin, id="child2-other-mixin"),
            rx.heading(Child2.child_mixin, id="child2-child-mixin"),
            rx.heading(Child3.basevar, id="child3-basevar"),
            rx.heading(Child3.mixin, id="child3-mixin"),
            rx.heading(Child3.other_mixin, id="child3-other-mixin"),
            rx.heading(Child3.childvar, id="child3-childvar"),
            rx.heading(Child3.child_mixin, id="child3-child-mixin"),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="session")
def state_inheritance(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start StateInheritance app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp(f"state_inheritance"),
        app_source=StateInheritance,  # type: ignore
    ) as harness:
        yield harness


@pytest.fixture
def driver(state_inheritance: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the state_inheritance app.

    Args:
        state_inheritance: harness for StateInheritance app

    Yields:
        WebDriver instance.
    """
    assert state_inheritance.app_instance is not None, "app is not running"
    driver = state_inheritance.frontend()
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture()
def token(state_inheritance: AppHarness, driver: WebDriver) -> str:
    """Get a function that returns the active token.

    Args:
        state_inheritance: harness for StateInheritance app.
        driver: WebDriver instance.

    Returns:
        The token for the connected client
    """
    assert state_inheritance.app_instance is not None
    token_input = driver.find_element(By.ID, "token")
    assert token_input

    # wait for the backend connection to send the token
    token = state_inheritance.poll_for_value(token_input, timeout=DEFAULT_TIMEOUT * 2)
    assert token is not None

    return token


def test_state_inheritance(
    state_inheritance: AppHarness,
    driver: WebDriver,
    token: str,
):
    """Test that background tasks work as expected.

    Args:
        state_inheritance: harness for StateInheritance app.
        driver: WebDriver instance.
        token: The token for the connected client.
    """
    assert state_inheritance.app_instance is not None

    base1_mixin = driver.find_element(By.ID, "base1-mixin")
    assert base1_mixin.text == "mixin"

    base1_basevar = driver.find_element(By.ID, "base1-basevar")
    assert base1_basevar.text == "basevar1"

    base1_child_mixin = driver.find_element(By.ID, "base1-child-mixin")
    assert base1_child_mixin.text == "child_mixin"

    base2_basevar = driver.find_element(By.ID, "base2-basevar")
    assert base2_basevar.text == "basevar2"

    child1_basevar = driver.find_element(By.ID, "child1-basevar")
    assert child1_basevar.text == "basevar1"

    child1_mixin = driver.find_element(By.ID, "child1-mixin")
    assert child1_mixin.text == "mixin"

    child1_other_mixin = driver.find_element(By.ID, "child1-other-mixin")
    assert child1_other_mixin.text == "other_mixin"

    child1_child_mixin = driver.find_element(By.ID, "child1-child-mixin")
    assert child1_child_mixin.text == "child_mixin"

    child2_basevar = driver.find_element(By.ID, "child2-basevar")
    assert child2_basevar.text == "basevar2"

    child2_mixin = driver.find_element(By.ID, "child2-mixin")
    assert child2_mixin.text == "mixin"

    child2_other_mixin = driver.find_element(By.ID, "child2-other-mixin")
    assert child2_other_mixin.text == "other_mixin"

    child2_child_mixin = driver.find_element(By.ID, "child2-child-mixin")
    assert child2_child_mixin.text == "child_mixin"

    child3_basevar = driver.find_element(By.ID, "child3-basevar")
    assert child3_basevar.text == "basevar2"

    child3_mixin = driver.find_element(By.ID, "child3-mixin")
    assert child3_mixin.text == "mixin"

    child3_other_mixin = driver.find_element(By.ID, "child3-other-mixin")
    assert child3_other_mixin.text == "other_mixin"

    child3_childvar = driver.find_element(By.ID, "child3-childvar")
    assert child3_childvar.text == "childvar"

    child3_child_mixin = driver.find_element(By.ID, "child3-child-mixin")
    assert child3_child_mixin.text == "child_mixin"
