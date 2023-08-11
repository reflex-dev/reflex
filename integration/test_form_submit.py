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

    app = rx.App(state=FormState)

    @app.add_page
    def index():
        return rx.vstack(
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
        assert form_submit.poll_for_clients()
        yield driver
    finally:
        driver.quit()


def test_submit(driver, form_submit: AppHarness):
    """Fill a form with various different output, submit it to backend and verify
    the output.

    Args:
        driver: selenium WebDriver open to the app
        form_submit: harness for FormSubmit app
    """
    assert form_submit.app_instance is not None, "app is not running"
    _, backend_state = list(form_submit.app_instance.state_manager.states.items())[0]

    name_input = driver.find_element(By.ID, "name_input")
    name_input.send_keys("foo")

    pin_inputs = driver.find_elements(By.CLASS_NAME, "chakra-pin-input")
    for pin_input in pin_inputs:
        pin_input.send_keys("5")

    number_input = driver.find_element(By.CLASS_NAME, "chakra-numberinput")
    buttons = number_input.find_elements(By.XPATH, "//div[@role='button']")
    buttons[1].click()
    buttons[1].click()
    buttons[1].click()

    checkbox_input = driver.find_element(By.CLASS_NAME, "chakra-checkbox__control")
    checkbox_input.click()

    switch_input = driver.find_element(By.CLASS_NAME, "chakra-switch__track")
    switch_input.click()

    radio_buttons = driver.find_elements(By.CLASS_NAME, "chakra-radio__control")
    radio_buttons[1].click()

    textarea_input = driver.find_element(By.CLASS_NAME, "chakra-textarea")
    textarea_input.send_keys("Some", Keys.ENTER, "Text")

    time.sleep(1)

    submit_input = driver.find_element(By.CLASS_NAME, "chakra-button")
    submit_input.click()

    print(backend_state.form_data)
    assert backend_state.form_data["name_input"] == "foo"
    assert backend_state.form_data["pin_input"] == ["5", "5", "5", "5"]
    assert backend_state.form_data["number_input"] == "-3"
    assert backend_state.form_data["bool_input"] is True
    assert backend_state.form_data["bool_input2"] is True
    assert backend_state.form_data["slider_input"] == "50"
    assert backend_state.form_data["range_input"] == ["25", "75"]
    assert backend_state.form_data["radio_input"] == "option2"
    assert backend_state.form_data["select_input"] == "option1"
    assert backend_state.form_data["text_area_input"] == "Some\nText"
