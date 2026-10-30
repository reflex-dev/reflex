"""Integration tests for TypedDict-annotated form submissions."""

import functools
import json
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect
from reflex_base.utils import format

from reflex.testing import AppHarness


def TypedDictFormSubmit(form_component):
    """App with a form using a TypedDict-annotated on_submit handler.

    Args:
        form_component: The form component expression to use.
    """
    from typing import NotRequired, TypedDict

    import reflex as rx

    class ContactData(TypedDict):
        name: str
        email: str
        message: NotRequired[str]
        topics: list[str]
        subscribe: bool
        bounds: list[str]

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
                    rx.el.input(type="hidden", name="topics", value="news"),
                    rx.el.input(type="hidden", name="topics", value="events"),
                    rx.checkbox("Subscribe", name="subscribe"),
                    rx.slider(name="bounds", default_value=[20, 80]),
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
        form_component: The form component expression to use.
    """
    from typing import Generic, TypeVar

    from typing_extensions import TypedDict

    import reflex as rx

    T = TypeVar("T")

    class BaseData(TypedDict, total=False):
        nickname: str

    class TaggedData(TypedDict, Generic[T]):
        tags: T
        maybe: T | None

    class SignupData(BaseData, TaggedData[list[str]]):
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
                    rx.el.input(type="hidden", name="tags", value="first"),
                    rx.el.input(type="hidden", name="tags", value="second"),
                    rx.el.input(type="hidden", name="maybe", disabled=True),
                    rx.button("Submit", type_="submit"),
                ),
                on_submit=FormState.form_submit,
                custom_attrs={"action": "/invalid"},
            ),
            rx.text(FormState.form_data.to_string(), id="form-data"),
            rx.spacer(),
            height="100vh",
        )


_CONTACT_FIELDS = {
    "inputs": {"name": "Alice", "email": "alice@example.com"},
    "textarea": "Hello there",
    "expected": {
        "name": "Alice",
        "email": "alice@example.com",
        "message": "Hello there",
        "topics": ["news", "events"],
        "subscribe": False,
        "bounds": ["20", "80"],
    },
}
_INHERITED_FIELDS = {
    "inputs": {"email": "user@example.com", "nickname": "cooluser"},
    "textarea": None,
    "expected": {
        "email": "user@example.com",
        "nickname": "cooluser",
        "tags": ["first", "second"],
        "maybe": None,
    },
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
    ids=["typeddict-radix", "typeddict-html", "inherited-html"],
)
def typeddict_form(
    request, tmp_path_factory
) -> Generator[tuple[AppHarness, dict], None, None]:
    """Start the selected TypedDict form app.

    Yields:
        The running app harness and its expected field data.
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


def test_typeddict_form_submit(
    typeddict_form: tuple[AppHarness, dict], page: Page
) -> None:
    """Submit each form variant and verify normalized data and URL behavior."""
    harness, fields = typeddict_form
    assert harness.frontend_url is not None
    page.goto(harness.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    for input_name, input_value in fields["inputs"].items():
        page.locator(f'[name="{input_name}"]').fill(input_value)

    if fields["textarea"] is not None:
        page.locator("textarea").fill(fields["textarea"])

    previous_url = page.url
    page.get_by_role("button", name="Submit", exact=True).click()

    form_data_element = page.locator("#form-data")
    expect(form_data_element).not_to_have_text("{}")
    form_data = json.loads(form_data_element.inner_text())
    assert isinstance(form_data, dict)
    form_data = format.collect_form_dict_names(form_data)

    for key, expected_value in fields["expected"].items():
        assert form_data[key] == expected_value, f"Mismatch for {key!r}"

    expect(page).to_have_url(previous_url)
