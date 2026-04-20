"""Integration tests for TypedDict-annotated form submissions."""

import asyncio
import functools
import json
from collections.abc import Generator

import pytest
from reflex_base.utils import format
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness


def TypedDictFormSubmit(form_component):
    """App with a form using a TypedDict-annotated on_submit handler.

    Args:
        form_component: The str name of the form component to use.
    """
    from typing import TypedDict

    from typing_extensions import NotRequired

    import reflex as rx

    class ContactData(TypedDict):
        name: str
        email: str
        message: NotRequired[str]

    class FormState(rx.State):
        form_data: rx.Field[dict] = rx.field(default_factory=dict)

        def form_submit(self, form_data: ContactData):
            self.form_data = dict(form_data)

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
                    rx.input(name="name"),
                    rx.input(name="email"),
                    rx.text_area(name="message"),
                    rx.button("Submit", type_="submit"),
                ),
                on_submit=FormState.form_submit,
                custom_attrs={"action": "/invalid"},
            ),
            rx.text(FormState.form_data.to_string(), id="form-data"),
            rx.spacer(),
            height="100vh",
        )


def TypedDictInheritedFormSubmit(form_component):
    """App with a form using an inherited TypedDict with optional parent fields.

    Args:
        form_component: The str name of the form component to use.
    """
    from typing import TypedDict

    import reflex as rx

    class BaseData(TypedDict, total=False):
        nickname: str

    class SignupData(BaseData):
        email: str

    class FormState(rx.State):
        form_data: rx.Field[dict] = rx.field(default_factory=dict)

        def form_submit(self, form_data: SignupData):
            self.form_data = dict(form_data)

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
                    rx.input(name="email"),
                    rx.input(name="nickname"),
                    rx.button("Submit", type_="submit"),
                ),
                on_submit=FormState.form_submit,
                custom_attrs={"action": "/invalid"},
            ),
            rx.text(FormState.form_data.to_string(), id="form-data"),
            rx.spacer(),
            height="100vh",
        )


# Each variant carries its own input actions and expected output.
_CONTACT_FIELDS = {
    "inputs": {"name": "Alice", "email": "alice@example.com"},
    "textarea": "Hello there",
    "expected": {
        "name": "Alice",
        "email": "alice@example.com",
        "message": "Hello there",
    },
}
_INHERITED_FIELDS = {
    "inputs": {"email": "user@example.com", "nickname": "cooluser"},
    "textarea": None,
    "expected": {"email": "user@example.com", "nickname": "cooluser"},
}


@pytest.fixture(
    scope="module",
    params=[
        (
            functools.partial(TypedDictFormSubmit, form_component="rx.form.root"),
            _CONTACT_FIELDS,
        ),
        (
            functools.partial(TypedDictFormSubmit, form_component="rx.el.form"),
            _CONTACT_FIELDS,
        ),
        (
            functools.partial(
                TypedDictInheritedFormSubmit, form_component="rx.el.form"
            ),
            _INHERITED_FIELDS,
        ),
    ],
    ids=[
        "typeddict-radix",
        "typeddict-html",
        "inherited-html",
    ],
)
def typeddict_form(
    request, tmp_path_factory
) -> Generator[tuple[AppHarness, dict], None, None]:
    """Start a TypedDict form app at tmp_path via AppHarness.

    Args:
        request: pytest request fixture
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance and its test field config
    """
    app_source, fields = request.param
    param_id = request._pyfuncitem.callspec.id.replace("-", "_")
    with AppHarness.create(
        root=tmp_path_factory.mktemp("typeddict_form"),
        app_source=app_source,
        app_name=app_source.func.__name__ + f"_{param_id}",
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness, fields


@pytest.fixture
def driver(typeddict_form: tuple[AppHarness, dict]):
    """Get an instance of the browser open to the app.

    Args:
        typeddict_form: harness and fields for the TypedDict form app

    Yields:
        WebDriver instance.
    """
    harness, _ = typeddict_form
    driver = harness.frontend()
    try:
        yield driver
    finally:
        driver.quit()


@pytest.mark.asyncio
async def test_typeddict_form_submit(driver, typeddict_form: tuple[AppHarness, dict]):
    """Fill a TypedDict-backed form, submit it, and verify the data arrives.

    Args:
        driver: selenium WebDriver open to the app
        typeddict_form: harness and fields for the app
    """
    harness, fields = typeddict_form
    assert harness.app_instance is not None, "app is not running"

    token_input = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "token")
    )
    token = harness.poll_for_value(token_input)
    assert token

    for input_name, input_value in fields["inputs"].items():
        el = driver.find_element(By.NAME, input_name)
        el.send_keys(input_value)

    if fields["textarea"] is not None:
        textarea = driver.find_element(By.TAG_NAME, "textarea")
        textarea.send_keys(fields["textarea"])

    await asyncio.sleep(0.5)

    prev_url = driver.current_url

    submit_btn = driver.find_element(By.CLASS_NAME, "rt-Button")
    submit_btn.click()

    harness.poll_for_content(
        driver.find_element(By.ID, "form-data"), exp_not_equal="{}"
    )
    form_data = json.loads(driver.find_element(By.ID, "form-data").text)
    assert isinstance(form_data, dict)
    form_data = format.collect_form_dict_names(form_data)

    for key, expected_value in fields["expected"].items():
        assert form_data[key] == expected_value, f"Mismatch for {key!r}"

    # submitting the form should NOT change the url (preventDefault)
    assert driver.current_url == prev_url
