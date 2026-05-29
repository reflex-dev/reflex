"""Test that per-component state scaffold works and operates independently."""

from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness

from . import utils


def ComponentStateApp():
    """App using per component state."""
    from typing import Generic, TypeVar

    import reflex as rx

    E = TypeVar("E")

    class MultiCounter(rx.ComponentState, Generic[E]):
        """ComponentState style."""

        count: int = 0
        _be: E
        _be_int: int
        _be_str: str = "42"

        @rx.event
        def increment(self):
            self.count += 1
            self._be = self.count  # ty:ignore[invalid-assignment]

        @rx.event
        def assert_be(self, value: E):
            assert self._backend_vars != self.backend_vars
            assert self._be == int(value)  # ty:ignore[invalid-argument-type]

        @rx.event
        def assert_be_none(self):
            assert self._backend_vars == {
                name: value
                for name, value in self.backend_vars.items()
                if name not in self.inherited_backend_vars
            }
            assert self._be is None

        @rx.event
        def assert_be_int(self, value: int):
            assert self._be_int == value

        @rx.event
        def assert_be_str(self, value: str):
            assert self._be_str == value

        @classmethod
        def get_component(cls, *children, **props):
            eid = props.get("id", "default")
            return rx.vstack(
                *children,
                rx.heading(cls.count, id=f"count-{eid}"),
                rx.button(
                    "Increment",
                    on_click=cls.increment,
                    id=f"button-{eid}",
                ),
                rx.form(
                    rx.input(id=f"{eid}-assert-be-value", name="be_value"),
                    rx.button(
                        "Assert _be",
                        id=f"{eid}-assert-be",
                    ),
                    on_submit=lambda fd: cls.assert_be(fd.to(dict)["be_value"]),
                    reset_on_submit=True,
                ),
                rx.button(
                    "Assert _be_none",
                    id=f"{eid}-assert-be-none",
                    on_click=cls.assert_be_none,
                ),
                rx.button(
                    "Assert _be_int == 0",
                    id=f"{eid}-assert-be-int",
                    on_click=cls.assert_be_int(0),
                ),
                rx.button(
                    "Assert _be_str == '42'",
                    id=f"{eid}-assert-be-str",
                    on_click=cls.assert_be_str("42"),
                ),
                **props,
            )

    def multi_counter_func(id: str = "default") -> rx.Component:
        """Local-substate style.

        Args:
            id: identifier for this instance

        Returns:
            A new instance of the component with its own state.
        """

        class _Counter(rx.State):
            count: int = 0

            @rx.event
            def increment(self):
                self.count += 1

        return rx.vstack(
            rx.heading(_Counter.count, id=f"count-{id}"),
            rx.button(
                "Increment",
                on_click=_Counter.increment,
                id=f"button-{id}",
            ),
            State=_Counter,
        )

    app = rx.App()  # noqa: F841

    @rx.page()
    def index():
        mc_a = MultiCounter.create(id="a")
        mc_b = MultiCounter.create(id="b")
        mc_c = multi_counter_func(id="c")
        mc_d = multi_counter_func(id="d")
        assert mc_a.State != mc_b.State
        assert mc_c.State != mc_d.State
        return rx.vstack(
            mc_a,
            mc_b,
            mc_c,
            mc_d,
            rx.button(
                "Inc A",
                on_click=mc_a.State.increment,  # ty:ignore[unresolved-attribute]
                id="inc-a",
            ),
            rx.text(
                mc_a.State.get_name() if mc_a.State is not None else "",
                id="a_state_name",
            ),
            rx.text(
                mc_b.State.get_name() if mc_b.State is not None else "",
                id="b_state_name",
            ),
        )


@pytest.fixture
def component_state_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start ComponentStateApp app at tmp_path via AppHarness.

    Args:
        tmp_path: pytest tmp_path fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=ComponentStateApp,
    ) as harness:
        yield harness


def test_component_state_app(component_state_app: AppHarness):
    """Increment counters independently.

    Args:
        component_state_app: harness for ComponentStateApp app
    """
    assert component_state_app.app_instance is not None, "app is not running"
    driver = component_state_app.frontend()

    ss = utils.SessionStorage(driver)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"

    count_a = driver.find_element(By.ID, "count-a")
    count_b = driver.find_element(By.ID, "count-b")
    button_a = driver.find_element(By.ID, "button-a")
    button_b = driver.find_element(By.ID, "button-b")
    button_inc_a = driver.find_element(By.ID, "inc-a")

    # Check that backend vars in mixins are okay
    driver.find_element(By.ID, "a-assert-be-none").click()
    driver.find_element(By.ID, "a-assert-be-int").click()
    driver.find_element(By.ID, "a-assert-be-str").click()

    assert count_a.text == "0"

    button_a.click()
    assert component_state_app.poll_for_content(count_a, exp_not_equal="0") == "1"

    button_a.click()
    assert component_state_app.poll_for_content(count_a, exp_not_equal="1") == "2"

    button_inc_a.click()
    assert component_state_app.poll_for_content(count_a, exp_not_equal="2") == "3"

    driver.find_element(By.ID, "a-assert-be-value").send_keys("3")
    driver.find_element(By.ID, "a-assert-be").click()
    driver.find_element(By.ID, "b-assert-be-none").click()

    assert count_b.text == "0"

    button_b.click()
    assert component_state_app.poll_for_content(count_b, exp_not_equal="0") == "1"

    button_b.click()
    assert component_state_app.poll_for_content(count_b, exp_not_equal="1") == "2"

    driver.find_element(By.ID, "b-assert-be-value").send_keys("2")
    driver.find_element(By.ID, "b-assert-be").click()

    # Check locally-defined substate style
    count_c = driver.find_element(By.ID, "count-c")
    count_d = driver.find_element(By.ID, "count-d")
    button_c = driver.find_element(By.ID, "button-c")
    button_d = driver.find_element(By.ID, "button-d")

    assert component_state_app.poll_for_content(count_c, exp_not_equal="") == "0"
    assert component_state_app.poll_for_content(count_d, exp_not_equal="") == "0"
    button_c.click()
    assert component_state_app.poll_for_content(count_c, exp_not_equal="0") == "1"
    assert component_state_app.poll_for_content(count_d, exp_not_equal="") == "0"
    button_c.click()
    assert component_state_app.poll_for_content(count_c, exp_not_equal="1") == "2"
    assert component_state_app.poll_for_content(count_d, exp_not_equal="") == "0"
    button_d.click()
    assert component_state_app.poll_for_content(count_c, exp_not_equal="1") == "2"
    assert component_state_app.poll_for_content(count_d, exp_not_equal="0") == "1"
