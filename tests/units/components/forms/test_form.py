from typing import TypedDict

import pytest
from reflex_base.event import EventChain, prevent_default
from reflex_base.utils.exceptions import EventHandlerValueError
from reflex_base.vars.base import Var
from reflex_components_core.el.elements.forms import Form as HTMLForm
from reflex_components_core.el.elements.forms import Input
from reflex_components_radix.primitives.form import Form
from typing_extensions import NotRequired

import reflex as rx


def test_render_on_submit():
    """Test that on_submit event chain is rendered as a separate function."""
    submit_it = Var(
        _js_expr="submit_it",
        _var_type=EventChain,
    )
    f = Form.create(on_submit=submit_it)
    exp_submit_name = f"handleSubmit_{f.handle_submit_unique_name}"  # pyright: ignore [reportAttributeAccessIssue]
    assert f"onSubmit:{exp_submit_name}" in f.render()["props"]


def test_render_no_on_submit():
    """A form without on_submit should render a prevent_default handler."""
    f = Form.create()
    assert isinstance(f.event_triggers["on_submit"], EventChain)
    assert len(f.event_triggers["on_submit"].events) == 1
    assert f.event_triggers["on_submit"].events[0] == prevent_default


@pytest.mark.parametrize("form_factory", [HTMLForm.create, Form.create])
def test_on_submit_accepts_typed_dict_form_data(form_factory):
    """TypedDict-annotated submit handlers should be accepted."""

    class SignupData(TypedDict):
        name: str
        email: str

    class SignupState(rx.State):
        @rx.event
        def on_submit(self, form_data: SignupData):
            pass

    form = form_factory(
        Input.create(name="name"),
        Input.create(name="email"),
        on_submit=SignupState.on_submit,
    )

    assert isinstance(form.event_triggers["on_submit"], EventChain)


def test_on_submit_accepts_id_backed_typed_dict_form_data():
    """Static ids that are mirrored into form_data should satisfy TypedDict keys."""

    class SignupData(TypedDict):
        email_input: str

    class SignupState(rx.State):
        @rx.event
        def on_submit(self, form_data: SignupData):
            pass

    form = HTMLForm.create(
        Input.create(id="email_input"),
        on_submit=SignupState.on_submit,
    )

    assert isinstance(form.event_triggers["on_submit"], EventChain)


def test_on_submit_accepts_typed_dict_with_optional_fields():
    """Optional TypedDict keys should not be required in the form."""

    class SignupData(TypedDict):
        email: str
        nickname: NotRequired[str]

    class SignupState(rx.State):
        @rx.event
        def on_submit(self, form_data: SignupData):
            pass

    form = HTMLForm.create(
        Input.create(name="email"),
        on_submit=SignupState.on_submit,
    )

    assert isinstance(form.event_triggers["on_submit"], EventChain)


def test_on_submit_allows_extra_typed_dict_form_fields():
    """Forms may include more fields than the TypedDict requires."""

    class SignupData(TypedDict):
        email: str

    class SignupState(rx.State):
        @rx.event
        def on_submit(self, form_data: SignupData):
            pass

    form = HTMLForm.create(
        Input.create(name="email"),
        Input.create(name="nickname"),
        on_submit=SignupState.on_submit,
    )

    assert isinstance(form.event_triggers["on_submit"], EventChain)


def test_on_submit_resolves_typed_dict_after_bound_args():
    """The final submit payload parameter should still resolve after binding args."""

    class SignupData(TypedDict):
        email: str

    class SignupState(rx.State):
        @rx.event
        def on_submit(self, source: str, form_data: SignupData):
            pass

    form = HTMLForm.create(
        Input.create(name="email"),
        on_submit=SignupState.on_submit("marketing"),  # pyright: ignore [reportCallIssue]
    )

    assert isinstance(form.event_triggers["on_submit"], EventChain)


def test_on_submit_typed_dict_missing_fields_raises_helpful_error():
    """Missing required TypedDict keys should produce a focused compile-time error."""

    class SignupData(TypedDict):
        fname: str
        lname: str
        email: str

    class SignupState(rx.State):
        @rx.event
        def on_submit(self, form_data: SignupData):
            pass

    with pytest.raises(EventHandlerValueError) as err:
        HTMLForm.create(
            Input.create(name="email"),
            on_submit=SignupState.on_submit,
        )

    error = str(err.value)
    assert "Form field mismatch for on_submit handler" in error
    assert "SignupState.on_submit" in error
    assert "SignupData" in error
    assert '"fname"' in error
    assert '"lname"' in error
    assert '"email"' in error
    assert "Matching fields present in the form" in error


def test_on_submit_typed_dict_skips_dynamic_field_identifiers():
    """Dynamic field names should skip strict validation instead of raising."""

    class SignupData(TypedDict):
        email: str

    class SignupState(rx.State):
        @rx.event
        def on_submit(self, form_data: SignupData):
            pass

    form = HTMLForm.create(
        Input.create(name=Var(_js_expr="dynamic_name", _var_type=str)),
        on_submit=SignupState.on_submit,
    )

    assert isinstance(form.event_triggers["on_submit"], EventChain)
