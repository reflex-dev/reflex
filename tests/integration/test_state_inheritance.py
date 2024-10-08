"""Test state inheritance."""

from __future__ import annotations

from contextlib import suppress
from typing import Generator

import pytest
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.by import By

from reflex.testing import DEFAULT_TIMEOUT, AppHarness, WebDriver


def get_alert_or_none(driver: WebDriver) -> Alert | None:
    """Switch to an alert if present.

    Args:
        driver: WebDriver instance.

    Returns:
        The alert if present, otherwise None.
    """
    with suppress(NoAlertPresentException):
        return driver.switch_to.alert


def raises_alert(driver: WebDriver, element: str) -> None:
    """Click an element and check that an alert is raised.

    Args:
        driver: WebDriver instance.
        element: The element to click.
    """
    btn = driver.find_element(By.ID, element)
    btn.click()
    alert = AppHarness._poll_for(lambda: get_alert_or_none(driver))
    assert isinstance(alert, Alert)
    assert alert.text == "clicked"
    alert.accept()


def StateInheritance():
    """Test that state inheritance works as expected."""
    import reflex as rx

    class ChildMixin(rx.State, mixin=True):
        child_mixin: str = "child_mixin"

        @rx.var
        def computed_child_mixin(self) -> str:
            return "computed_child_mixin"

    class Mixin(ChildMixin, mixin=True):
        mixin: str = "mixin"

        @rx.var
        def computed_mixin(self) -> str:
            return "computed_mixin"

        def on_click_mixin(self):
            return rx.call_script("alert('clicked')")

    class OtherMixin(rx.State, mixin=True):
        other_mixin: str = "other_mixin"
        other_mixin_clicks: int = 0

        @rx.var
        def computed_other_mixin(self) -> str:
            return self.other_mixin

        def on_click_other_mixin(self):
            self.other_mixin_clicks += 1
            self.other_mixin = (
                f"{self.__class__.__name__}.clicked.{self.other_mixin_clicks}"
            )

    class Base1(Mixin, rx.State):
        _base1: str = "_base1"
        base1: str = "base1"

        @rx.var
        def computed_basevar(self) -> str:
            return "computed_basevar1"

        @rx.var
        def computed_backend_vars_base1(self) -> str:
            return self._base1

    class Base2(rx.State):
        _base2: str = "_base2"
        base2: str = "base2"

        @rx.var
        def computed_basevar(self) -> str:
            return "computed_basevar2"

        @rx.var
        def computed_backend_vars_base2(self) -> str:
            return self._base2

    class Child1(Base1, OtherMixin):
        pass

    class Child2(Base2, Mixin, OtherMixin):
        pass

    class Child3(Child2):
        _child3: str = "_child3"
        child3: str = "child3"

        @rx.var
        def computed_childvar(self) -> str:
            return "computed_childvar"

        @rx.var
        def computed_backend_vars_child3(self) -> str:
            return f"{self._base2}.{self._child3}"

    def index() -> rx.Component:
        return rx.vstack(
            rx.input(
                id="token", value=Base1.router.session.client_token, is_read_only=True
            ),
            # Base 1 (Mixin, ChildMixin)
            rx.heading(Base1.computed_mixin, id="base1-computed_mixin"),
            rx.heading(Base1.computed_basevar, id="base1-computed_basevar"),
            rx.heading(Base1.computed_child_mixin, id="base1-computed-child-mixin"),
            rx.heading(Base1.base1, id="base1-base1"),
            rx.heading(Base1.child_mixin, id="base1-child-mixin"),
            rx.button(
                "Base1.on_click_mixin",
                on_click=Base1.on_click_mixin,  # type: ignore
                id="base1-mixin-btn",
            ),
            rx.heading(
                Base1.computed_backend_vars_base1, id="base1-computed_backend_vars"
            ),
            # Base 2 (no mixins)
            rx.heading(Base2.computed_basevar, id="base2-computed_basevar"),
            rx.heading(Base2.base2, id="base2-base2"),
            rx.heading(
                Base2.computed_backend_vars_base2, id="base2-computed_backend_vars"
            ),
            # Child 1 (Mixin, ChildMixin, OtherMixin)
            rx.heading(Child1.computed_basevar, id="child1-computed_basevar"),
            rx.heading(Child1.computed_mixin, id="child1-computed_mixin"),
            rx.heading(Child1.computed_other_mixin, id="child1-other-mixin"),
            rx.heading(Child1.computed_child_mixin, id="child1-computed-child-mixin"),
            rx.heading(Child1.base1, id="child1-base1"),
            rx.heading(Child1.other_mixin, id="child1-other_mixin"),
            rx.heading(Child1.child_mixin, id="child1-child-mixin"),
            rx.button(
                "Child1.on_click_other_mixin",
                on_click=Child1.on_click_other_mixin,  # type: ignore
                id="child1-other-mixin-btn",
            ),
            # Child 2 (Mixin, ChildMixin, OtherMixin)
            rx.heading(Child2.computed_basevar, id="child2-computed_basevar"),
            rx.heading(Child2.computed_mixin, id="child2-computed_mixin"),
            rx.heading(Child2.computed_other_mixin, id="child2-other-mixin"),
            rx.heading(Child2.computed_child_mixin, id="child2-computed-child-mixin"),
            rx.heading(Child2.base2, id="child2-base2"),
            rx.heading(Child2.other_mixin, id="child2-other_mixin"),
            rx.heading(Child2.child_mixin, id="child2-child-mixin"),
            rx.button(
                "Child2.on_click_mixin",
                on_click=Child2.on_click_mixin,  # type: ignore
                id="child2-mixin-btn",
            ),
            rx.button(
                "Child2.on_click_other_mixin",
                on_click=Child2.on_click_other_mixin,  # type: ignore
                id="child2-other-mixin-btn",
            ),
            # Child 3 (Mixin, ChildMixin, OtherMixin)
            rx.heading(Child3.computed_basevar, id="child3-computed_basevar"),
            rx.heading(Child3.computed_mixin, id="child3-computed_mixin"),
            rx.heading(Child3.computed_other_mixin, id="child3-other-mixin"),
            rx.heading(Child3.computed_childvar, id="child3-computed_childvar"),
            rx.heading(Child3.computed_child_mixin, id="child3-computed-child-mixin"),
            rx.heading(Child3.child3, id="child3-child3"),
            rx.heading(Child3.base2, id="child3-base2"),
            rx.heading(Child3.other_mixin, id="child3-other_mixin"),
            rx.heading(Child3.child_mixin, id="child3-child-mixin"),
            rx.button(
                "Child3.on_click_mixin",
                on_click=Child3.on_click_mixin,  # type: ignore
                id="child3-mixin-btn",
            ),
            rx.button(
                "Child3.on_click_other_mixin",
                on_click=Child3.on_click_other_mixin,  # type: ignore
                id="child3-other-mixin-btn",
            ),
            rx.heading(
                Child3.computed_backend_vars_child3, id="child3-computed_backend_vars"
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
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

    # Initial State values Test
    # Base 1
    base1_mixin = driver.find_element(By.ID, "base1-computed_mixin")
    assert base1_mixin.text == "computed_mixin"

    base1_computed_basevar = driver.find_element(By.ID, "base1-computed_basevar")
    assert base1_computed_basevar.text == "computed_basevar1"

    base1_computed_child_mixin = driver.find_element(
        By.ID, "base1-computed-child-mixin"
    )
    assert base1_computed_child_mixin.text == "computed_child_mixin"

    base1_base1 = driver.find_element(By.ID, "base1-base1")
    assert base1_base1.text == "base1"

    base1_computed_backend_vars = driver.find_element(
        By.ID, "base1-computed_backend_vars"
    )
    assert base1_computed_backend_vars.text == "_base1"

    base1_child_mixin = driver.find_element(By.ID, "base1-child-mixin")
    assert base1_child_mixin.text == "child_mixin"

    # Base 2
    base2_computed_basevar = driver.find_element(By.ID, "base2-computed_basevar")
    assert base2_computed_basevar.text == "computed_basevar2"

    base2_base2 = driver.find_element(By.ID, "base2-base2")
    assert base2_base2.text == "base2"

    base2_computed_backend_vars = driver.find_element(
        By.ID, "base2-computed_backend_vars"
    )
    assert base2_computed_backend_vars.text == "_base2"

    # Child 1
    child1_computed_basevar = driver.find_element(By.ID, "child1-computed_basevar")
    assert child1_computed_basevar.text == "computed_basevar1"

    child1_mixin = driver.find_element(By.ID, "child1-computed_mixin")
    assert child1_mixin.text == "computed_mixin"

    child1_computed_other_mixin = driver.find_element(By.ID, "child1-other-mixin")
    assert child1_computed_other_mixin.text == "other_mixin"

    child1_computed_child_mixin = driver.find_element(
        By.ID, "child1-computed-child-mixin"
    )
    assert child1_computed_child_mixin.text == "computed_child_mixin"

    child1_base1 = driver.find_element(By.ID, "child1-base1")
    assert child1_base1.text == "base1"

    child1_other_mixin = driver.find_element(By.ID, "child1-other_mixin")
    assert child1_other_mixin.text == "other_mixin"

    child1_child_mixin = driver.find_element(By.ID, "child1-child-mixin")
    assert child1_child_mixin.text == "child_mixin"

    # Child 2
    child2_computed_basevar = driver.find_element(By.ID, "child2-computed_basevar")
    assert child2_computed_basevar.text == "computed_basevar2"

    child2_mixin = driver.find_element(By.ID, "child2-computed_mixin")
    assert child2_mixin.text == "computed_mixin"

    child2_computed_other_mixin = driver.find_element(By.ID, "child2-other-mixin")
    assert child2_computed_other_mixin.text == "other_mixin"

    child2_computed_child_mixin = driver.find_element(
        By.ID, "child2-computed-child-mixin"
    )
    assert child2_computed_child_mixin.text == "computed_child_mixin"

    child2_base2 = driver.find_element(By.ID, "child2-base2")
    assert child2_base2.text == "base2"

    child2_other_mixin = driver.find_element(By.ID, "child2-other_mixin")
    assert child2_other_mixin.text == "other_mixin"

    child2_child_mixin = driver.find_element(By.ID, "child2-child-mixin")
    assert child2_child_mixin.text == "child_mixin"

    # Child 3
    child3_computed_basevar = driver.find_element(By.ID, "child3-computed_basevar")
    assert child3_computed_basevar.text == "computed_basevar2"

    child3_mixin = driver.find_element(By.ID, "child3-computed_mixin")
    assert child3_mixin.text == "computed_mixin"

    child3_computed_other_mixin = driver.find_element(By.ID, "child3-other-mixin")
    assert child3_computed_other_mixin.text == "other_mixin"

    child3_computed_childvar = driver.find_element(By.ID, "child3-computed_childvar")
    assert child3_computed_childvar.text == "computed_childvar"

    child3_computed_child_mixin = driver.find_element(
        By.ID, "child3-computed-child-mixin"
    )
    assert child3_computed_child_mixin.text == "computed_child_mixin"

    child3_child3 = driver.find_element(By.ID, "child3-child3")
    assert child3_child3.text == "child3"

    child3_base2 = driver.find_element(By.ID, "child3-base2")
    assert child3_base2.text == "base2"

    child3_other_mixin = driver.find_element(By.ID, "child3-other_mixin")
    assert child3_other_mixin.text == "other_mixin"

    child3_child_mixin = driver.find_element(By.ID, "child3-child-mixin")
    assert child3_child_mixin.text == "child_mixin"

    child3_computed_backend_vars = driver.find_element(
        By.ID, "child3-computed_backend_vars"
    )
    assert child3_computed_backend_vars.text == "_base2._child3"

    # Event Handler Tests
    raises_alert(driver, "base1-mixin-btn")
    raises_alert(driver, "child2-mixin-btn")
    raises_alert(driver, "child3-mixin-btn")

    child1_other_mixin_btn = driver.find_element(By.ID, "child1-other-mixin-btn")
    child1_other_mixin_btn.click()
    child1_other_mixin_value = state_inheritance.poll_for_content(
        child1_other_mixin, exp_not_equal="other_mixin"
    )
    child1_computed_mixin_value = state_inheritance.poll_for_content(
        child1_computed_other_mixin, exp_not_equal="other_mixin"
    )
    assert child1_other_mixin_value == "Child1.clicked.1"
    assert child1_computed_mixin_value == "Child1.clicked.1"

    child2_other_mixin_btn = driver.find_element(By.ID, "child2-other-mixin-btn")
    child2_other_mixin_btn.click()
    child2_other_mixin_value = state_inheritance.poll_for_content(
        child2_other_mixin, exp_not_equal="other_mixin"
    )
    child2_computed_mixin_value = state_inheritance.poll_for_content(
        child2_computed_other_mixin, exp_not_equal="other_mixin"
    )
    child3_other_mixin_value = state_inheritance.poll_for_content(
        child3_other_mixin, exp_not_equal="other_mixin"
    )
    child3_computed_mixin_value = state_inheritance.poll_for_content(
        child3_computed_other_mixin, exp_not_equal="other_mixin"
    )
    assert child2_other_mixin_value == "Child2.clicked.1"
    assert child2_computed_mixin_value == "Child2.clicked.1"
    assert child3_other_mixin_value == "Child2.clicked.1"
    assert child3_computed_mixin_value == "Child2.clicked.1"

    child3_other_mixin_btn = driver.find_element(By.ID, "child3-other-mixin-btn")
    child3_other_mixin_btn.click()
    child2_other_mixin_value = state_inheritance.poll_for_content(
        child2_other_mixin, exp_not_equal="Child2.clicked.1"
    )
    child2_computed_mixin_value = state_inheritance.poll_for_content(
        child2_computed_other_mixin, exp_not_equal="Child2.clicked.1"
    )
    child3_other_mixin_value = state_inheritance.poll_for_content(
        child3_other_mixin, exp_not_equal="Child2.clicked.1"
    )
    child3_computed_mixin_value = state_inheritance.poll_for_content(
        child3_computed_other_mixin, exp_not_equal="Child2.clicked.1"
    )
    assert child2_other_mixin_value == "Child2.clicked.2"
    assert child2_computed_mixin_value == "Child2.clicked.2"
    assert child3_other_mixin.text == "Child2.clicked.2"
    assert child3_computed_other_mixin.text == "Child2.clicked.2"
