"""Integration tests for text input and related components."""

from typing import Generator

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from reflex.testing import AppHarness


def FullyControlledInput():
    """App using a fully controlled input with implicit debounce wrapper."""
    import reflex as rx

    class State(rx.State):
        text: str = "initial"

    app = rx.App(state=rx.State)

    @app.add_page
    def index():
        return rx.fragment(
            rx.input(
                value=State.router.session.client_token, is_read_only=True, id="token"
            ),
            rx.input(
                id="debounce_input_input",
                on_change=State.set_text,  # type: ignore
                value=State.text,
            ),
            rx.input(value=State.text, id="value_input", is_read_only=True),
            rx.input(on_change=State.set_text, id="on_change_input"),  # type: ignore
            rx.el.input(
                value=State.text,
                id="plain_value_input",
                disabled=True,
                _disabled={"width": "42px"},
            ),
            rx.input(default_value="default", id="default_input"),
            rx.el.input(
                type="text", default_value="default plain", id="plain_default_input"
            ),
            rx.checkbox(default_checked=True, id="default_checkbox"),
            rx.el.input(
                type="checkbox", default_checked=True, id="plain_default_checkbox"
            ),
            rx.button(
                "CLEAR", on_click=rx.set_value("on_change_input", ""), id="clear"
            ),
        )


@pytest.fixture()
def fully_controlled_input(tmp_path) -> Generator[AppHarness, None, None]:
    """Start FullyControlledInput app at tmp_path via AppHarness.

    Args:
        tmp_path: pytest tmp_path fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=FullyControlledInput,  # type: ignore
    ) as harness:
        yield harness


@pytest.mark.asyncio
async def test_fully_controlled_input(fully_controlled_input: AppHarness):
    """Type text after moving cursor. Update text on backend.

    Args:
        fully_controlled_input: harness for FullyControlledInput app
    """
    assert fully_controlled_input.app_instance is not None, "app is not running"
    driver = fully_controlled_input.frontend()

    # get a reference to the connected client
    token_input = driver.find_element(By.ID, "token")
    assert token_input

    # wait for the backend connection to send the token
    token = fully_controlled_input.poll_for_value(token_input)
    assert token

    state_name = fully_controlled_input.get_state_name("_state")
    full_state_name = fully_controlled_input.get_full_state_name(["_state"])

    async def get_state_text():
        state = await fully_controlled_input.get_state(f"{token}_{full_state_name}")
        return state.substates[state_name].text

    # ensure defaults are set correctly
    assert (
        fully_controlled_input.poll_for_value(
            driver.find_element(By.ID, "default_input")
        )
        == "default"
    )
    assert (
        fully_controlled_input.poll_for_value(
            driver.find_element(By.ID, "plain_default_input")
        )
        == "default plain"
    )
    assert (
        fully_controlled_input.poll_for_value(
            driver.find_element(By.ID, "default_checkbox")
        )
        == "on"
    )
    assert (
        fully_controlled_input.poll_for_value(
            driver.find_element(By.ID, "plain_default_checkbox")
        )
        == "on"
    )

    # find the input and wait for it to have the initial state value
    debounce_input = driver.find_element(By.ID, "debounce_input_input")
    value_input = driver.find_element(By.ID, "value_input")
    on_change_input = driver.find_element(By.ID, "on_change_input")
    plain_value_input = driver.find_element(By.ID, "plain_value_input")
    clear_button = driver.find_element(By.ID, "clear")
    assert fully_controlled_input.poll_for_value(debounce_input) == "initial"
    assert fully_controlled_input.poll_for_value(value_input) == "initial"
    assert fully_controlled_input.poll_for_value(plain_value_input) == "initial"
    assert plain_value_input.value_of_css_property("width") == "42px"

    # move cursor to home, then to the right and type characters
    debounce_input.send_keys(*([Keys.ARROW_LEFT] * len("initial")), Keys.ARROW_RIGHT)
    debounce_input.send_keys("foo")
    assert AppHarness._poll_for(
        lambda: fully_controlled_input.poll_for_value(value_input) == "ifoonitial"
    )
    assert debounce_input.get_attribute("value") == "ifoonitial"
    assert await get_state_text() == "ifoonitial"
    assert fully_controlled_input.poll_for_value(plain_value_input) == "ifoonitial"

    # clear the input on the backend
    async with fully_controlled_input.modify_state(
        f"{token}_{full_state_name}"
    ) as state:
        state.substates[state_name].text = ""
    assert await get_state_text() == ""
    assert (
        fully_controlled_input.poll_for_value(
            debounce_input, exp_not_equal="ifoonitial"
        )
        == ""
    )

    # type more characters
    debounce_input.send_keys("getting testing done")
    assert AppHarness._poll_for(
        lambda: fully_controlled_input.poll_for_value(value_input)
        == "getting testing done"
    )
    assert debounce_input.get_attribute("value") == "getting testing done"
    assert await get_state_text() == "getting testing done"
    assert (
        fully_controlled_input.poll_for_value(plain_value_input)
        == "getting testing done"
    )

    # type into the on_change input
    on_change_input.send_keys("overwrite the state")
    assert AppHarness._poll_for(
        lambda: fully_controlled_input.poll_for_value(value_input)
        == "overwrite the state"
    )
    assert debounce_input.get_attribute("value") == "overwrite the state"
    assert on_change_input.get_attribute("value") == "overwrite the state"
    assert await get_state_text() == "overwrite the state"
    assert (
        fully_controlled_input.poll_for_value(plain_value_input)
        == "overwrite the state"
    )

    clear_button.click()
    assert AppHarness._poll_for(lambda: on_change_input.get_attribute("value") == "")
    # potential bug: clearing the on_change field doesn't itself trigger on_change
    # assert backend_state.text == ""
    # assert debounce_input.get_attribute("value") == ""
    # assert value_input.get_attribute("value") == ""
