"""Integration tests for forms."""

import functools
import time
from typing import Generator

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from reflex.testing import AppHarness
from reflex.utils import format


def FormSubmit(form_component):
    """App with a form using on_submit.

    Args:
        form_component: The str name of the form component to use.
    """
    from typing import Dict, List

    import reflex as rx

    class FormState(rx.State):
        form_data: Dict = {}

        var_options: List[str] = ["option3", "option4"]

        def form_submit(self, form_data: Dict):
            self.form_data = form_data

    app = rx.App(state=rx.State)

    @app.add_page
    def index():
        return rx.vstack(
            rx.chakra.input(
                value=FormState.router.session.client_token,
                is_read_only=True,
                id="token",
            ),
            eval(form_component)(
                rx.vstack(
                    rx.chakra.input(id="name_input"),
                    rx.hstack(rx.chakra.pin_input(length=4, id="pin_input")),
                    rx.chakra.number_input(id="number_input"),
                    rx.checkbox(id="bool_input"),
                    rx.switch(id="bool_input2"),
                    rx.checkbox(id="bool_input3"),
                    rx.switch(id="bool_input4"),
                    rx.slider(id="slider_input", default_value=[50], width="100%"),
                    rx.chakra.range_slider(id="range_input"),
                    rx.radio(["option1", "option2"], id="radio_input"),
                    rx.radio(FormState.var_options, id="radio_input_var"),
                    rx.chakra.select(["option1", "option2"], id="select_input"),
                    rx.chakra.select(FormState.var_options, id="select_input_var"),
                    rx.text_area(id="text_area_input"),
                    rx.chakra.input(
                        id="debounce_input",
                        debounce_timeout=0,
                        on_change=rx.console_log,
                    ),
                    rx.button("Submit", type_="submit"),
                ),
                on_submit=FormState.form_submit,
                custom_attrs={"action": "/invalid"},
            ),
            rx.spacer(),
            height="100vh",
        )


def FormSubmitName(form_component):
    """App with a form using on_submit.

    Args:
        form_component: The str name of the form component to use.
    """
    from typing import Dict, List

    import reflex as rx

    class FormState(rx.State):
        form_data: Dict = {}
        val: str = "foo"
        options: List[str] = ["option1", "option2"]

        def form_submit(self, form_data: Dict):
            self.form_data = form_data

    app = rx.App(state=rx.State)

    @app.add_page
    def index():
        return rx.vstack(
            rx.chakra.input(
                value=FormState.router.session.client_token,
                is_read_only=True,
                id="token",
            ),
            eval(form_component)(
                rx.vstack(
                    rx.chakra.input(name="name_input"),
                    rx.hstack(rx.chakra.pin_input(length=4, name="pin_input")),
                    rx.chakra.number_input(name="number_input"),
                    rx.checkbox(name="bool_input"),
                    rx.switch(name="bool_input2"),
                    rx.checkbox(name="bool_input3"),
                    rx.switch(name="bool_input4"),
                    rx.slider(name="slider_input", default_value=[50], width="100%"),
                    rx.chakra.range_slider(name="range_input"),
                    rx.radio(FormState.options, name="radio_input"),
                    rx.select(
                        FormState.options,
                        name="select_input",
                        default_value=FormState.options[0],
                    ),
                    rx.text_area(name="text_area_input"),
                    rx.chakra.input_group(
                        rx.chakra.input_left_element(rx.icon(tag="chevron_right")),
                        rx.chakra.input(
                            name="debounce_input",
                            debounce_timeout=0,
                            on_change=rx.console_log,
                        ),
                        rx.chakra.input_right_element(rx.icon(tag="chevron_left")),
                    ),
                    rx.chakra.button_group(
                        rx.button("Submit", type_="submit"),
                        rx.icon_button(FormState.val, icon=rx.icon(tag="plus")),
                        variant="outline",
                        is_attached=True,
                    ),
                ),
                on_submit=FormState.form_submit,
                custom_attrs={"action": "/invalid"},
            ),
            rx.spacer(),
            height="100vh",
        )


@pytest.fixture(
    scope="module",
    params=[
        functools.partial(FormSubmit, form_component="rx.form.root"),
        functools.partial(FormSubmitName, form_component="rx.form.root"),
        functools.partial(FormSubmit, form_component="rx.el.form"),
        functools.partial(FormSubmitName, form_component="rx.el.form"),
        functools.partial(FormSubmit, form_component="rx.chakra.form"),
        functools.partial(FormSubmitName, form_component="rx.chakra.form"),
    ],
    ids=[
        "id-radix",
        "name-radix",
        "id-html",
        "name-html",
        "id-chakra",
        "name-chakra",
    ],
)
def form_submit(request, tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start FormSubmit app at tmp_path via AppHarness.

    Args:
        request: pytest request fixture
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    param_id = request._pyfuncitem.callspec.id.replace("-", "_")
    with AppHarness.create(
        root=tmp_path_factory.mktemp("form_submit"),
        app_source=request.param,  # type: ignore
        app_name=request.param.func.__name__ + f"_{param_id}",
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
    by = By.ID if form_submit.app_source is FormSubmit else By.NAME

    # get a reference to the connected client
    token_input = driver.find_element(By.ID, "token")
    assert token_input

    # wait for the backend connection to send the token
    token = form_submit.poll_for_value(token_input)
    assert token

    name_input = driver.find_element(by, "name_input")
    name_input.send_keys("foo")

    pin_inputs = driver.find_elements(By.CLASS_NAME, "chakra-pin-input")
    pin_values = ["8", "1", "6", "4"]
    for i, pin_input in enumerate(pin_inputs):
        pin_input.send_keys(pin_values[i])

    number_input = driver.find_element(By.CLASS_NAME, "chakra-numberinput")
    buttons = number_input.find_elements(By.XPATH, "//div[@role='button']")
    for _ in range(3):
        buttons[1].click()

    checkbox_input = driver.find_element(By.XPATH, "//button[@role='checkbox']")
    checkbox_input.click()

    switch_input = driver.find_element(By.XPATH, "//button[@role='switch']")
    switch_input.click()

    radio_buttons = driver.find_elements(By.XPATH, "//button[@role='radio']")
    radio_buttons[1].click()

    textarea_input = driver.find_element(By.TAG_NAME, "textarea")
    textarea_input.send_keys("Some", Keys.ENTER, "Text")

    debounce_input = driver.find_element(by, "debounce_input")
    debounce_input.send_keys("bar baz")

    time.sleep(1)

    prev_url = driver.current_url

    submit_input = driver.find_element(By.CLASS_NAME, "rt-Button")
    submit_input.click()

    async def get_form_data():
        return (
            (await form_submit.get_state(f"{token}_state.form_state"))
            .substates["form_state"]
            .form_data
        )

    # wait for the form data to arrive at the backend
    form_data = await AppHarness._poll_for_async(get_form_data)
    assert isinstance(form_data, dict)

    form_data = format.collect_form_dict_names(form_data)

    assert form_data["name_input"] == "foo"
    assert form_data["pin_input"] == pin_values
    assert form_data["number_input"] == "-3"
    assert form_data["bool_input"]
    assert form_data["bool_input2"]
    assert not form_data.get("bool_input3", False)
    assert not form_data.get("bool_input4", False)

    assert form_data["slider_input"] == "50"
    assert form_data["range_input"] == ["25", "75"]
    assert form_data["radio_input"] == "option2"
    assert form_data["select_input"] == "option1"
    assert form_data["text_area_input"] == "Some\nText"
    assert form_data["debounce_input"] == "bar baz"

    # submitting the form should NOT change the url (preventDefault on_submit event)
    assert driver.current_url == prev_url
