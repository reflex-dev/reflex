"""Integration tests for text input and related components."""
import time
from typing import Generator

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from reflex.testing import AppHarness


def FullyControlledInput():
    """App using a fully controlled input with debounce wrapper."""
    import reflex as rx

    class State(rx.State):
        text: str = "initial"

    app = rx.App(state=State)

    @app.add_page
    def index():
        return rx.debounce_input(
            rx.input(
                value=State.text,
                on_change=State.set_text,  # type: ignore
            ),
            debounce_timeout=0,
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
    assert len(fully_controlled_input.poll_for_clients()) == 1
    token, backend_state = list(
        fully_controlled_input.app_instance.state_manager.states.items()
    )[0]

    # find the input and wait for it to have the initial state value
    text_input = driver.find_element(By.TAG_NAME, "input")
    assert fully_controlled_input.poll_for_value(text_input) == "initial"

    # move cursor to home, then to the right and type characters
    text_input.send_keys(Keys.HOME, Keys.ARROW_RIGHT)
    text_input.send_keys("foo")
    assert text_input.get_attribute("value") == "ifoonitial"
    assert backend_state.text == "ifoonitial"

    # clear the input on the backend
    backend_state.text = ""
    fully_controlled_input.app_instance.state_manager.set_state(token, backend_state)
    await fully_controlled_input.emit_state_updates()
    assert backend_state.text == ""
    assert (
        fully_controlled_input.poll_for_value(text_input, exp_not_equal="ifoonitial")
        == ""
    )

    # type more characters
    text_input.send_keys("getting testing done")
    time.sleep(0.1)
    assert text_input.get_attribute("value") == "getting testing done"
    assert backend_state.text == "getting testing done"
