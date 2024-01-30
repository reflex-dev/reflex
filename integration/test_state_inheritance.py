"""Test state inheritance."""

from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import DEFAULT_TIMEOUT, AppHarness, WebDriver


def StateInheritance():
    """Test that state inheritance works as expected."""
    import reflex as rx

    class ChildMixin:
        child_mixin: str = "child_mixin"

        @rx.var
        def computed_child_mixin(self) -> str:
            return "computed_child_mixin"

    class Mixin(ChildMixin):
        mixin: str = "mixin"

        @rx.var
        def computed_mixin(self) -> str:
            return "computed_mixin"

    class OtherMixin(rx.Base):
        other_mixin: str = "other_mixin"

        @rx.var
        def computed_other_mixin(self) -> str:
            return "computed_other_mixin"

    class Base1(rx.State, Mixin):
        base1: str = "base1"

        @rx.var
        def computed_basevar(self) -> str:
            return "computed_basevar1"

    class Base2(rx.State):
        base2: str = "base2"

        @rx.var
        def computed_basevar(self) -> str:
            return "computed_basevar2"

    class Child1(Base1, OtherMixin):
        pass

    class Child2(Base2, Mixin, OtherMixin):
        pass

    class Child3(Child2):
        child3: str = "child3"

        @rx.var
        def computed_childvar(self) -> str:
            return "computed_childvar"

    def index() -> rx.Component:
        return rx.vstack(
            rx.input(
                id="token", value=Base1.router.session.client_token, is_read_only=True
            ),
            rx.heading(Base1.computed_mixin, id="base1-computed_mixin"),
            rx.heading(Base1.computed_basevar, id="base1-computed_basevar"),
            rx.heading(Base1.computed_child_mixin, id="base1-child-mixin"),
            rx.heading(Base1.base1, id="base1-base1"),
            rx.heading(Base1.mixin, id="base1-mixin"),
            rx.heading(Base1.child_mixin, id="base1-child_mixin"),
            rx.heading(Base2.computed_basevar, id="base2-computed_basevar"),
            rx.heading(Base2.base2, id="base2-base2"),
            rx.heading(Child1.computed_basevar, id="child1-computed_basevar"),
            rx.heading(Child1.computed_mixin, id="child1-computed_mixin"),
            rx.heading(Child1.computed_other_mixin, id="child1-other-mixin"),
            rx.heading(Child1.computed_child_mixin, id="child1-child-mixin"),
            rx.heading(Child1.base1, id="child1-base1"),
            rx.heading(Child1.mixin, id="child1-mixin"),
            rx.heading(Child1.other_mixin, id="child1-other_mixin"),
            rx.heading(Child1.child_mixin, id="child1-child_mixin"),
            rx.heading(Child2.computed_basevar, id="child2-computed_basevar"),
            rx.heading(Child2.computed_mixin, id="child2-computed_mixin"),
            rx.heading(Child2.computed_other_mixin, id="child2-other-mixin"),
            rx.heading(Child2.computed_child_mixin, id="child2-child-mixin"),
            rx.heading(Child2.base2, id="child2-base2"),
            rx.heading(Child2.mixin, id="child2-mixin"),
            rx.heading(Child2.other_mixin, id="child2-other_mixin"),
            rx.heading(Child2.child_mixin, id="child2-child_mixin"),
            rx.heading(Child3.computed_basevar, id="child3-computed_basevar"),
            rx.heading(Child3.computed_mixin, id="child3-computed_mixin"),
            rx.heading(Child3.computed_other_mixin, id="child3-other-mixin"),
            rx.heading(Child3.computed_childvar, id="child3-computed_childvar"),
            rx.heading(Child3.computed_child_mixin, id="child3-child-mixin"),
            rx.heading(Child3.child3, id="child3-child3"),
            rx.heading(Child3.base2, id="child3-base2"),
            rx.heading(Child3.mixin, id="child3-mixin"),
            rx.heading(Child3.other_mixin, id="child3-other_mixin"),
            rx.heading(Child3.child_mixin, id="child3-child_mixin"),
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

    base1_mixin = driver.find_element(By.ID, "base1-computed_mixin")
    assert base1_mixin.text == "computed_mixin"

    base1_computed_basevar = driver.find_element(By.ID, "base1-computed_basevar")
    assert base1_computed_basevar.text == "computed_basevar1"

    base1_computed_child_mixin = driver.find_element(By.ID, "base1-child-mixin")
    assert base1_computed_child_mixin.text == "computed_child_mixin"

    base1_base1 = driver.find_element(By.ID, "base1-base1")
    assert base1_base1.text == "base1"

    base1_mixin = driver.find_element(By.ID, "base1-mixin")
    assert base1_mixin.text == "mixin"

    base1_child_mixin = driver.find_element(By.ID, "base1-child_mixin")
    assert base1_child_mixin.text == "child_mixin"

    base2_computed_basevar = driver.find_element(By.ID, "base2-computed_basevar")
    assert base2_computed_basevar.text == "computed_basevar2"

    base2_base2 = driver.find_element(By.ID, "base2-base2")
    assert base2_base2.text == "base2"

    child1_computed_basevar = driver.find_element(By.ID, "child1-computed_basevar")
    assert child1_computed_basevar.text == "computed_basevar1"

    child1_mixin = driver.find_element(By.ID, "child1-computed_mixin")
    assert child1_mixin.text == "computed_mixin"

    child1_computed_other_mixin = driver.find_element(By.ID, "child1-other-mixin")
    assert child1_computed_other_mixin.text == "computed_other_mixin"

    child1_computed_child_mixin = driver.find_element(By.ID, "child1-child-mixin")
    assert child1_computed_child_mixin.text == "computed_child_mixin"

    child1_base1 = driver.find_element(By.ID, "child1-base1")
    assert child1_base1.text == "base1"

    child1_mixin = driver.find_element(By.ID, "child1-mixin")
    assert child1_mixin.text == "mixin"

    child1_other_mixin = driver.find_element(By.ID, "child1-other_mixin")
    assert child1_other_mixin.text == "other_mixin"

    child1_child_mixin = driver.find_element(By.ID, "child1-child_mixin")
    assert child1_child_mixin.text == "child_mixin"

    child2_computed_basevar = driver.find_element(By.ID, "child2-computed_basevar")
    assert child2_computed_basevar.text == "computed_basevar2"

    child2_mixin = driver.find_element(By.ID, "child2-computed_mixin")
    assert child2_mixin.text == "computed_mixin"

    child2_computed_other_mixin = driver.find_element(By.ID, "child2-other-mixin")
    assert child2_computed_other_mixin.text == "computed_other_mixin"

    child2_computed_child_mixin = driver.find_element(By.ID, "child2-child-mixin")
    assert child2_computed_child_mixin.text == "computed_child_mixin"

    child2_base2 = driver.find_element(By.ID, "child2-base2")
    assert child2_base2.text == "base2"

    child2_mixin = driver.find_element(By.ID, "child2-mixin")
    assert child2_mixin.text == "mixin"

    child2_other_mixin = driver.find_element(By.ID, "child2-other_mixin")
    assert child2_other_mixin.text == "other_mixin"

    child2_child_mixin = driver.find_element(By.ID, "child2-child_mixin")
    assert child2_child_mixin.text == "child_mixin"

    child3_computed_basevar = driver.find_element(By.ID, "child3-computed_basevar")
    assert child3_computed_basevar.text == "computed_basevar2"

    child3_mixin = driver.find_element(By.ID, "child3-computed_mixin")
    assert child3_mixin.text == "computed_mixin"

    child3_computed_other_mixin = driver.find_element(By.ID, "child3-other-mixin")
    assert child3_computed_other_mixin.text == "computed_other_mixin"

    child3_computed_childvar = driver.find_element(By.ID, "child3-computed_childvar")
    assert child3_computed_childvar.text == "computed_childvar"

    child3_computed_child_mixin = driver.find_element(By.ID, "child3-child-mixin")
    assert child3_computed_child_mixin.text == "computed_child_mixin"

    child3_child3 = driver.find_element(By.ID, "child3-child3")
    assert child3_child3.text == "child3"

    child3_base2 = driver.find_element(By.ID, "child3-base2")
    assert child3_base2.text == "base2"

    child3_mixin = driver.find_element(By.ID, "child3-mixin")
    assert child3_mixin.text == "mixin"

    child3_other_mixin = driver.find_element(By.ID, "child3-other_mixin")
    assert child3_other_mixin.text == "other_mixin"

    child3_child_mixin = driver.find_element(By.ID, "child3-child_mixin")
    assert child3_child_mixin.text == "child_mixin"
