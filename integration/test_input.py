"""Integration tests for text input and related components."""
import time
from typing import Generator

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from nextpy.core.testing import AppHarness


def FullyControlledInput():
    """App using a fully controlled input with implicit debounce wrapper."""
    import nextpy as xt

    class State(xt.State):
        text: str = "initial"

    app = xt.App(state=State)

    @app.add_page
    def index():
        return xt.fragment(
            xt.input(
                value=State.router.session.client_token, is_read_only=True, id="token"
            ),
            xt.input(
                id="debounce_input_input",
                on_change=State.set_text,  # type: ignore
                value=State.text,
            ),
            xt.input(value=State.text, id="value_input", is_read_only=True),
            xt.input(on_change=State.set_text, id="on_change_input"),  # type: ignore
            xt.button("CLEAR", on_click=xt.set_value("on_change_input", "")),
        )

    app.compile()


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

    # find the input and wait for it to have the initial state value
    debounce_input = driver.find_element(By.ID, "debounce_input_input")
    value_input = driver.find_element(By.ID, "value_input")
    on_change_input = driver.find_element(By.ID, "on_change_input")
    clear_button = driver.find_element(By.TAG_NAME, "button")
    assert fully_controlled_input.poll_for_value(debounce_input) == "initial"
    assert fully_controlled_input.poll_for_value(value_input) == "initial"

    # move cursor to home, then to the right and type characters
    debounce_input.send_keys(Keys.HOME, Keys.ARROW_RIGHT)
    debounce_input.send_keys("foo")
    time.sleep(0.5)
    assert debounce_input.get_attribute("value") == "ifoonitial"
    assert (await fully_controlled_input.get_state(token)).text == "ifoonitial"
    assert fully_controlled_input.poll_for_value(value_input) == "ifoonitial"

    # clear the input on the backend
    async with fully_controlled_input.modify_state(token) as state:
        state.text = ""
    assert (await fully_controlled_input.get_state(token)).text == ""
    assert (
        fully_controlled_input.poll_for_value(
            debounce_input, exp_not_equal="ifoonitial"
        )
        == ""
    )

    # type more characters
    debounce_input.send_keys("getting testing done")
    time.sleep(0.5)
    assert debounce_input.get_attribute("value") == "getting testing done"
    assert (
        await fully_controlled_input.get_state(token)
    ).text == "getting testing done"
    assert fully_controlled_input.poll_for_value(value_input) == "getting testing done"

    # type into the on_change input
    on_change_input.send_keys("overwrite the state")
    time.sleep(0.5)
    assert debounce_input.get_attribute("value") == "overwrite the state"
    assert on_change_input.get_attribute("value") == "overwrite the state"
    assert (await fully_controlled_input.get_state(token)).text == "overwrite the state"
    assert fully_controlled_input.poll_for_value(value_input) == "overwrite the state"

    clear_button.click()
    time.sleep(0.5)
    assert on_change_input.get_attribute("value") == ""
    # potential bug: clearing the on_change field doesn't itself trigger on_change
    # assert backend_state.text == ""
    # assert debounce_input.get_attribute("value") == ""
    # assert value_input.get_attribute("value") == ""
