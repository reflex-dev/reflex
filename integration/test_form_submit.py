"""Integration tests for forms."""
import time
from typing import Generator

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from reflex.testing import AppHarness


def FormSubmit():
    """App with a form using on_submit."""
    import reflex as rx

    class FormState(rx.State):
        form_data: dict = {}

        def form_submit(self, form_data: dict):
            self.form_data = form_data

        @rx.var
        def token(self) -> str:
            return self.get_token()

    app = rx.App(state=FormState)

    @app.add_page
    def index():
        return rx.vstack(
            rx.input(value=FormState.token, is_read_only=True, id="token"),
            rx.form(
                rx.vstack(
                    rx.input(id="name_input"),
                    rx.hstack(rx.pin_input(length=4, id="pin_input")),
                    rx.number_input(id="number_input"),
                    rx.checkbox(id="bool_input"),
                    rx.switch(id="bool_input2"),
                    rx.slider(id="slider_input"),
                    rx.range_slider(id="range_input"),
                    rx.radio_group(["option1", "option2"], id="radio_input"),
                    rx.select(["option1", "option2"], id="select_input"),
                    rx.text_area(id="text_area_input"),
                    rx.input(
                        id="debounce_input",
                        debounce_timeout=0,
                        on_change=rx.console_log,
                    ),
                    rx.button("Submit", type_="submit"),
                ),
                on_submit=FormState.form_submit,
            ),
            rx.spacer(),
            height="100vh",
        )

    app.compile()


@pytest.fixture(scope="session")
def form_submit(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start FormSubmit app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("form_submit"),
        app_source=FormSubmit,  # type: ignore
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture
def driver(form_submit: AppHarness):
    """GEt an instance of the browser open to the form_submit app.

    Args:
        form_submit: harness for ServerSideEvent app

    Yields:
        WebDriver instance.
    """
    driver = form_submit.frontend()
    try:
        yield driver
    finally:
        driver.quit()


@pytest.mark.asyncio
async def test_submit(driver, form_submit: AppHarness):
    """Fill a form with various different output, submit it to backend and verify
    the output.

    Args:
        driver: selenium WebDriver open to the app
        form_submit: harness for FormSubmit app
    """
    assert form_submit.app_instance is not None, "app is not running"

    # get a reference to the connected client
    token_input = driver.find_element(By.ID, "token")
    assert token_input

    # wait for the backend connection to send the token
    token = form_submit.poll_for_value(token_input)
    assert token

    name_input = driver.find_element(By.ID, "name_input")
    name_input.send_keys("foo")

    pin_inputs = driver.find_elements(By.CLASS_NAME, "chakra-pin-input")
    pin_values = ["8", "1", "6", "4"]
    for i, pin_input in enumerate(pin_inputs):
        pin_input.send_keys(pin_values[i])

    number_input = driver.find_element(By.CLASS_NAME, "chakra-numberinput")
    buttons = number_input.find_elements(By.XPATH, "//div[@role='button']")
    for _ in range(3):
        buttons[1].click()

    checkbox_input = driver.find_element(By.CLASS_NAME, "chakra-checkbox__control")
    checkbox_input.click()

    switch_input = driver.find_element(By.CLASS_NAME, "chakra-switch__track")
    switch_input.click()

    radio_buttons = driver.find_elements(By.CLASS_NAME, "chakra-radio__control")
    radio_buttons[1].click()

    textarea_input = driver.find_element(By.CLASS_NAME, "chakra-textarea")
    textarea_input.send_keys("Some", Keys.ENTER, "Text")

    debounce_input = driver.find_element(By.ID, "debounce_input")
    debounce_input.send_keys("bar baz")

    time.sleep(1)

    submit_input = driver.find_element(By.CLASS_NAME, "chakra-button")
    submit_input.click()

    async def get_form_data():
        return (await form_submit.get_state(token)).form_data

    # wait for the form data to arrive at the backend
    form_data = await AppHarness._poll_for_async(get_form_data)
    assert isinstance(form_data, dict)

    assert form_data["name_input"] == "foo"
    assert form_data["pin_input"] == pin_values
    assert form_data["number_input"] == "-3"
    assert form_data["bool_input"] is True
    assert form_data["bool_input2"] is True
    assert form_data["slider_input"] == "50"
    assert form_data["range_input"] == ["25", "75"]
    assert form_data["radio_input"] == "option2"
    assert form_data["select_input"] == "option1"
    assert form_data["text_area_input"] == "Some\nText"
    assert form_data["debounce_input"] == "bar baz"
