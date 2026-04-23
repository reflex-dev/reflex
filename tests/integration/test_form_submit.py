"""Integration tests for forms."""

import asyncio
import functools
import json
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect
from reflex_base.utils import format

from reflex.testing import AppHarness

from . import utils


def FormSubmit(form_component):
    """App with a form using on_submit.

    Args:
        form_component: The str name of the form component to use.
    """
    import reflex as rx

    class FormState(rx.State):
        form_data: rx.Field[dict] = rx.field(default_factory=dict)

        var_options: list[str] = ["option3", "option4"]

        def form_submit(self, form_data: dict):
            self.form_data = form_data

    app = rx.App()

    @app.add_page
    def index():
        return rx.vstack(
            rx.input(
                value=FormState.router.session.client_token,
                is_read_only=True,
                id="token",
            ),
            eval(form_component)(
                rx.vstack(
                    rx.input(id="name_input"),
                    rx.checkbox(id="bool_input"),
                    rx.switch(id="bool_input2"),
                    rx.checkbox(id="bool_input3"),
                    rx.switch(id="bool_input4"),
                    rx.slider(id="slider_input", default_value=[50], width="100%"),
                    rx.radio(["option1", "option2"], id="radio_input"),
                    rx.radio(FormState.var_options, id="radio_input_var"),
                    rx.select(
                        ["option1", "option2"],
                        name="select_input",
                        default_value="option1",
                    ),
                    rx.select(FormState.var_options, id="select_input_var"),
                    rx.text_area(id="text_area_input"),
                    rx.input(
                        id="debounce_input",
                        debounce_timeout=0,
                        on_change=rx.console_log,
                    ),
                    rx.button("Submit", type_="submit"),
                ),
                on_submit=FormState.form_submit,
                custom_attrs={"action": "/invalid"},
            ),
            rx.text(FormState.form_data.to_string(), id="form-data"),
            rx.spacer(),
            height="100vh",
        )


def FormSubmitName(form_component):
    """App with a form using on_submit.

    Args:
        form_component: The str name of the form component to use.
    """
    import reflex as rx

    class FormState(rx.State):
        form_data: rx.Field[dict] = rx.field(default_factory=dict)
        val: str = "foo"
        options: list[str] = ["option1", "option2"]

        def form_submit(self, form_data: dict):
            self.form_data = form_data

    app = rx.App()

    @app.add_page
    def index():
        return rx.vstack(
            rx.input(
                value=FormState.router.session.client_token,
                is_read_only=True,
                id="token",
            ),
            eval(form_component)(
                rx.vstack(
                    rx.input(name="name_input"),
                    rx.checkbox(name="bool_input"),
                    rx.switch(name="bool_input2"),
                    rx.checkbox(name="bool_input3"),
                    rx.switch(name="bool_input4"),
                    rx.slider(name="slider_input", default_value=[50], width="100%"),
                    rx.radio(FormState.options, name="radio_input"),
                    rx.select(
                        FormState.options,
                        name="select_input",
                        default_value=FormState.options[0],
                    ),
                    rx.text_area(name="text_area_input"),
                    rx.input(
                        name="debounce_input",
                        debounce_timeout=0,
                        on_change=rx.console_log,
                    ),
                    rx.button("Submit", type_="submit"),
                    rx.icon_button(rx.icon(tag="plus")),
                ),
                on_submit=FormState.form_submit,
                custom_attrs={"action": "/invalid"},
            ),
            rx.text(FormState.form_data.to_string(), id="form-data"),
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
    ],
    ids=[
        "id-radix",
        "name-radix",
        "id-html",
        "name-html",
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
        app_source=request.param,
        app_name=request.param.func.__name__ + f"_{param_id}",
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.mark.asyncio
async def test_submit(page: Page, form_submit: AppHarness):
    """Fill a form with various different output, submit it to backend and verify
    the output.

    Args:
        page: Playwright page.
        form_submit: harness for FormSubmit app
    """
    assert form_submit.app_instance is not None, "app is not running"
    assert form_submit.frontend_url is not None
    page.goto(form_submit.frontend_url)

    by_id = form_submit.app_source is FormSubmit

    def by_name_or_id(value: str):
        if by_id:
            return page.locator(f"id={value}")
        return page.locator(f"[name={value}]")

    # wait for the backend connection to send the token
    utils.poll_for_token(page)

    name_input = by_name_or_id("name_input")
    name_input.fill("foo")

    checkbox_input = page.locator("button[role='checkbox']")
    checkbox_input.click()

    switch_input = page.locator("button[role='switch']")
    switch_input.click()

    radio_buttons = page.locator("button[role='radio']").all()
    radio_buttons[1].click()

    textarea_input = page.locator("textarea")
    textarea_input.fill("Some\nText")

    debounce_input = by_name_or_id("debounce_input")
    debounce_input.fill("bar baz")

    await asyncio.sleep(1)

    prev_url = page.url

    submit_input = page.locator(".rt-Button").first
    submit_input.click()

    # wait for the form data to arrive at the backend
    form_data_locator = page.locator("#form-data")
    expect(form_data_locator).not_to_have_text("{}")
    form_data = json.loads(form_data_locator.text_content() or "")
    assert isinstance(form_data, dict)
    form_data = format.collect_form_dict_names(form_data)

    print(form_data)

    assert form_data["name_input"] == "foo"
    assert form_data["bool_input"]
    assert form_data["bool_input2"]
    assert not form_data.get("bool_input3", False)
    assert not form_data.get("bool_input4", False)

    assert form_data["slider_input"] == "50"
    assert form_data["radio_input"] == "option2"
    assert form_data["select_input"] == "option1"
    assert form_data["text_area_input"] == "Some\nText"
    assert form_data["debounce_input"] == "bar baz"

    # submitting the form should NOT change the url (preventDefault on_submit event)
    assert page.url == prev_url
