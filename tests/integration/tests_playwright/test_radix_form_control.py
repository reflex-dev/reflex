"""Integration tests for the controls ``rx.form.control`` renders.

Radix ``Form.Control`` renders an input or, with ``as_child``, the native form
control its child renders, and passes it the enclosing field's ``name`` and
the ``id`` its label points to. Every control the Python wrapper accepts must
receive both, submit under the field's name and take part in validation.
"""

import json
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

FIELD_NAMES = (
    "input",
    "controlled",
    "text_area",
    "el_input",
    "el_textarea",
    "el_select",
)


def RadixFormControlApp():
    """A Radix form with one field per kind of control."""
    import reflex as rx

    class State(rx.State):
        typed: rx.Field[str] = rx.field("")
        submitted: rx.Field[dict[str, str]] = rx.field(default_factory=dict)

        @rx.event
        def set_typed(self, value: str):
            self.typed = value

        @rx.event
        def on_submit(self, form_data: dict[str, str]):
            self.submitted = form_data

    def form_field(name: str, control: rx.Component) -> rx.Component:
        return rx.form.field(
            rx.form.label(name),
            rx.form.control(control),
            rx.form.message("Required", match="valueMissing", id=f"{name}-message"),
            name=name,
        )

    @rx.page("/")
    def index():
        return rx.vstack(
            rx.input(
                value=State.router.session.client_token, read_only=True, id="token"
            ),
            rx.form.root(
                form_field("input", rx.input(default_value="input value")),
                form_field(
                    "controlled",
                    rx.input(value=State.typed, on_change=State.set_typed),
                ),
                form_field("text_area", rx.text_area(required=True)),
                form_field("el_input", rx.el.input(default_value="native input")),
                form_field(
                    "el_textarea", rx.el.textarea(default_value="native textarea")
                ),
                form_field(
                    "el_select",
                    rx.el.select(
                        rx.el.option("Apple", value="apple"),
                        rx.el.option("Pear", value="pear"),
                        default_value="pear",
                    ),
                ),
                rx.form.submit(rx.button("Submit", id="submit"), as_child=True),
                on_submit=State.on_submit,
            ),
            rx.text(State.typed, id="typed"),
            rx.text(State.submitted.to_string(), id="submitted"),
        )

    app = rx.App()  # noqa: F841


@pytest.fixture(scope="module")
def form_control_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start RadixFormControlApp via AppHarness.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("radix_form_control"),
        app_source=RadixFormControlApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_form_controls_take_their_field_name(form_control_app: AppHarness, page: Page):
    """Each control carries its field's name, its label's id, and validates.

    Args:
        form_control_app: AppHarness running the test app.
        page: Playwright page.
    """
    assert form_control_app.frontend_url is not None

    page_errors: list[str] = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    page.goto(form_control_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    # The label resolves through the id Radix gives the control.
    for name in FIELD_NAMES:
        expect(page.get_by_label(name, exact=True)).to_have_attribute("name", name)

    # The required textarea blocks submission and shows its field's message.
    page.click("#submit")
    expect(page.locator("#text_area-message")).to_have_text("Required")
    expect(page.locator("#submitted")).to_have_text("{}")

    page.get_by_label("controlled", exact=True).fill("typed value")
    expect(page.locator("#typed")).to_have_text("typed value")
    page.get_by_label("text_area", exact=True).fill("textarea value")
    page.get_by_label("el_select", exact=True).select_option("apple")
    page.click("#submit")

    expect(page.locator("#text_area-message")).to_have_count(0)
    expect(page.locator("#submitted")).not_to_have_text("{}")
    assert json.loads(page.locator("#submitted").text_content() or "") == {
        "input": "input value",
        "controlled": "typed value",
        "text_area": "textarea value",
        "el_input": "native input",
        "el_textarea": "native textarea",
        "el_select": "apple",
    }
    assert page_errors == []
