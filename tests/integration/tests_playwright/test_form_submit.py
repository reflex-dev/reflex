"""Integration tests for forms."""

import functools
import json
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect
from reflex_base.utils import format

from reflex.testing import AppHarness

FORM_CONTENT_WRAPPER_ID = "form_content_wrapper"
FORM_ID = "form_id"


def FormSubmit(
    form_component,
    form_id=FORM_ID,
    form_content_wrapper_id=FORM_CONTENT_WRAPPER_ID,
):
    """App with a form using on_submit.

    Args:
        form_component: The str name of the form component to use.
        form_id: The form element ID.
        form_content_wrapper_id: The non-control wrapper ID.
    """
    from reflex_components_core.el.elements.base import BaseHTML

    import reflex as rx

    class NativeInput(BaseHTML):
        tag = "input"

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
                    rx.input(id="empty_input"),
                    NativeInput.create(
                        id="native_input", custom_attrs={"defaultValue": "native"}
                    ),
                    rx.checkbox(id="bool_input"),
                    rx.switch(id="bool_input2"),
                    rx.checkbox(id="bool_input3"),
                    rx.switch(id="bool_input4"),
                    rx.slider(id="slider_input", default_value=[50], width="100%"),
                    rx.radio(["option1", "option2"], id="radio_input"),
                    rx.radio_group(["u1", "u2"], id="radio_unset"),
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
                    id=form_content_wrapper_id,
                ),
                on_submit=FormState.form_submit,
                custom_attrs={"action": "/invalid"},
                id=form_id,
            ),
            rx.text(FormState.form_data.to_string(), id="form-data"),
            rx.spacer(),
            height="100vh",
        )


def FormSubmitName(
    form_component,
    form_id=FORM_ID,
    form_content_wrapper_id=FORM_CONTENT_WRAPPER_ID,
):
    """App with a form using on_submit.

    Args:
        form_component: The str name of the form component to use.
        form_id: The form element ID.
        form_content_wrapper_id: The non-control wrapper ID.
    """
    import reflex as rx

    class FormState(rx.State):
        form_data: rx.Field[dict] = rx.field(default_factory=dict)
        tags: rx.Field[list[str]] = rx.field(default_factory=list)
        val: str = "foo"
        options: list[str] = ["option1", "option2"]

        @rx.event
        def form_submit(self, form_data: dict):
            # A file input submits its contents as bytes.
            self.form_data = {
                name: value for name, value in form_data.items() if name != "attachment"
            }

        @rx.event
        def form_submit_all(self, form_data: rx.form.FormData[str, str]):
            self.tags = form_data.getlist("tag")

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
                    rx.input(name="empty_input"),
                    rx.el.input(type="hidden", name="tag", value="a"),
                    rx.el.input(type="hidden", name="tag", value="b"),
                    # Its File makes Socket.IO send the event as a binary packet.
                    rx.el.input(type="file", name="attachment"),
                    rx.checkbox(name="bool_input"),
                    rx.switch(name="bool_input2"),
                    rx.checkbox(name="bool_input3"),
                    rx.switch(name="bool_input4"),
                    rx.slider(name="slider_input", default_value=[50], width="100%"),
                    # Two thumbs submit their values as "range_input[]".
                    rx.slider(name="range_input", default_value=[20, 80], width="100%"),
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
                    id=form_content_wrapper_id,
                ),
                on_submit=[FormState.form_submit, FormState.form_submit_all],
                custom_attrs={"action": "/invalid"},
                id=form_id,
            ),
            rx.text(FormState.form_data.to_string(), id="form-data"),
            rx.text(FormState.tags.to_string(), id="tags"),
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


def test_submit(page: Page, form_submit: AppHarness):
    """Fill a form with various different output, submit it to backend and verify
    the output.

    Args:
        page: Playwright page.
        form_submit: harness for FormSubmit app
    """
    assert form_submit.frontend_url is not None
    page.goto(form_submit.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    input_selector = (
        "#name_input" if form_submit.app_source is FormSubmit else '[name="name_input"]'
    )
    page.locator(input_selector).fill("foo")
    page.get_by_role("checkbox").first.click()
    page.get_by_role("switch").first.click()
    page.get_by_role("radio").nth(1).click()
    page.locator("textarea").fill("Some\nText")
    debounce_selector = (
        "#debounce_input"
        if form_submit.app_source is FormSubmit
        else '[name="debounce_input"]'
    )
    page.locator(debounce_selector).fill("bar baz")

    prev_url = page.url
    page.get_by_role("button", name="Submit", exact=True).click()

    form_data_element = page.locator("#form-data")
    expect(form_data_element).not_to_have_text("{}")
    form_data = json.loads(form_data_element.inner_text())
    assert isinstance(form_data, dict)
    form_data = format.collect_form_dict_names(form_data)

    assert FORM_ID not in form_data
    assert FORM_CONTENT_WRAPPER_ID not in form_data
    assert form_data["name_input"] == "foo"
    assert form_data["empty_input"] == ""
    assert form_data["bool_input"]
    assert form_data["bool_input2"]
    assert not form_data.get("bool_input3", False)
    assert not form_data.get("bool_input4", False)

    assert form_data["slider_input"] == "50"
    assert form_data["radio_input"] == "option2"
    if form_submit.app_source is FormSubmit:
        assert form_data["radio_unset"] is None
        assert form_data["native_input"] == "native"
    assert form_data["select_input"] == "option1"
    assert form_data["text_area_input"] == "Some\nText"
    assert form_data["debounce_input"] == "bar baz"
    if form_submit.app_source is FormSubmitName:
        # A dict keeps the last value of a repeated name; FormData keeps them all.
        assert form_data["range_input[]"] == "80"
        assert form_data["tag"] == "b"
        tags = page.locator("#tags")
        expect(tags).not_to_have_text("[]")
        assert json.loads(tags.inner_text()) == ["a", "b"]

    # submitting the form should NOT change the url (preventDefault on_submit event)
    expect(page).to_have_url(prev_url)
