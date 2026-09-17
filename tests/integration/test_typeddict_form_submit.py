"""Integration tests for TypedDict-annotated form submissions."""

import functools
import json
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect
from reflex_base.utils import format

from reflex.testing import AppHarness

from .utils import poll_for_token


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


def test_typeddict_form_submit(page: Page, typeddict_form: tuple[AppHarness, dict]):
    """Fill a TypedDict-backed form and verify its submitted data.

    Args:
        page: Playwright page.
        typeddict_form: The app harness and its expected form fields.
    """
    harness, fields = typeddict_form
    assert harness.frontend_url is not None
    page.goto(harness.frontend_url)
    poll_for_token(page)
    for input_name, input_value in fields["inputs"].items():
        page.locator(f'[name="{input_name}"]').fill(input_value)
    if fields["textarea"] is not None:
        page.locator("textarea").fill(fields["textarea"])
    prev_url = page.url
    page.get_by_role("button", name="Submit", exact=True).click()
    result = page.locator("#form-data")
    expect(result).not_to_have_text("{}")
    form_data = json.loads(result.inner_text())
    assert isinstance(form_data, dict)
    form_data = format.collect_form_dict_names(form_data)
    for key, expected_value in fields["expected"].items():
        assert form_data[key] == expected_value, f"Mismatch for {key!r}"
    assert page.url == prev_url
