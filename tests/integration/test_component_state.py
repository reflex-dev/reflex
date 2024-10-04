"""Test that per-component state scaffold works and operates independently."""

from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.state import State, _substate_key
from reflex.testing import AppHarness

from . import utils


def ComponentStateApp():
    """App using per component state."""
    from typing import Generic, TypeVar

    import reflex as rx

    E = TypeVar("E")

    class MultiCounter(rx.ComponentState, Generic[E]):
        count: int = 0
        _be: E
        _be_int: int
        _be_str: str = "42"

        def increment(self):
            self.count += 1
            self._be = self.count  # type: ignore

        @classmethod
        def get_component(cls, *children, **props):
            return rx.vstack(
                *children,
                rx.heading(cls.count, id=f"count-{props.get('id', 'default')}"),
                rx.button(
                    "Increment",
                    on_click=cls.increment,
                    id=f"button-{props.get('id', 'default')}",
                ),
                **props,
            )

    app = rx.App(state=rx.State)  # noqa

    @rx.page()
    def index():
        mc_a = MultiCounter.create(id="a")
        mc_b = MultiCounter.create(id="b")
        assert mc_a.State != mc_b.State
        return rx.vstack(
            mc_a,
            mc_b,
            rx.button(
                "Inc A",
                on_click=mc_a.State.increment,  # type: ignore
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


@pytest.fixture()
def component_state_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start ComponentStateApp app at tmp_path via AppHarness.

    Args:
        tmp_path: pytest tmp_path fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=ComponentStateApp,  # type: ignore
    ) as harness:
        yield harness


@pytest.mark.asyncio
async def test_component_state_app(component_state_app: AppHarness):
    """Increment counters independently.

    Args:
        component_state_app: harness for ComponentStateApp app
    """
    assert component_state_app.app_instance is not None, "app is not running"
    driver = component_state_app.frontend()

    ss = utils.SessionStorage(driver)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"
    root_state_token = _substate_key(ss.get("token"), State)

    count_a = driver.find_element(By.ID, "count-a")
    count_b = driver.find_element(By.ID, "count-b")
    button_a = driver.find_element(By.ID, "button-a")
    button_b = driver.find_element(By.ID, "button-b")
    button_inc_a = driver.find_element(By.ID, "inc-a")

    # Check that backend vars in mixins are okay
    a_state_name = driver.find_element(By.ID, "a_state_name").text
    b_state_name = driver.find_element(By.ID, "b_state_name").text
    root_state = await component_state_app.get_state(root_state_token)
    a_state = root_state.substates[a_state_name]
    b_state = root_state.substates[b_state_name]
    assert a_state._backend_vars == a_state.backend_vars
    assert a_state._backend_vars == b_state._backend_vars
    assert a_state._backend_vars["_be"] is None
    assert a_state._backend_vars["_be_int"] == 0
    assert a_state._backend_vars["_be_str"] == "42"

    assert count_a.text == "0"

    button_a.click()
    assert component_state_app.poll_for_content(count_a, exp_not_equal="0") == "1"

    button_a.click()
    assert component_state_app.poll_for_content(count_a, exp_not_equal="1") == "2"

    button_inc_a.click()
    assert component_state_app.poll_for_content(count_a, exp_not_equal="2") == "3"

    root_state = await component_state_app.get_state(root_state_token)
    a_state = root_state.substates[a_state_name]
    b_state = root_state.substates[b_state_name]
    assert a_state._backend_vars != a_state.backend_vars
    assert a_state._be == a_state._backend_vars["_be"] == 3
    assert b_state._be is None
    assert b_state._backend_vars["_be"] is None

    assert count_b.text == "0"

    button_b.click()
    assert component_state_app.poll_for_content(count_b, exp_not_equal="0") == "1"

    button_b.click()
    assert component_state_app.poll_for_content(count_b, exp_not_equal="1") == "2"

    root_state = await component_state_app.get_state(root_state_token)
    a_state = root_state.substates[a_state_name]
    b_state = root_state.substates[b_state_name]
    assert b_state._backend_vars != b_state.backend_vars
    assert b_state._be == b_state._backend_vars["_be"] == 2
