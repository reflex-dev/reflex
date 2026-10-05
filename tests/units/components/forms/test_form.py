import logging
from typing import Any, TypedDict, TypeVar

import pytest
from reflex_base.event import EventChain, prevent_default
from reflex_base.utils.exceptions import (
    EventHandlerArgTypeMismatchError,
    EventHandlerValueError,
)
from reflex_base.utils.form import FormData
from reflex_base.vars.base import Var
from reflex_components_core.el.elements.forms import (
    AUTO_HEIGHT_JS,
    ENTER_KEY_SUBMIT_JS,
    Input,
    Textarea,
)
from reflex_components_core.el.elements.forms import Form as HTMLForm
from reflex_components_radix.primitives.form import Form, FormMessage
from typing_extensions import NotRequired

import reflex as rx
from reflex.compiler.utils import _root_only_custom_code

_T = TypeVar("_T")


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


def test_on_submit_rejects_id_backed_typed_dict_form_data():
    """Static ids are not submitted, so they cannot satisfy TypedDict keys."""

    class SignupData(TypedDict):
        email_input: str

    class SignupState(rx.State):
        @rx.event
        def on_submit(self, form_data: SignupData):
            pass

    with pytest.raises(EventHandlerValueError, match="email_input"):
        HTMLForm.create(
            Input.create(id="email_input"),
            on_submit=SignupState.on_submit,
        )


def test_on_submit_rejects_typed_dict_with_unresolved_field_types():
    """A TypedDict whose field types cannot be resolved fails at compile time."""

    class LooseData(TypedDict):
        tags: _T  # pyright: ignore[reportGeneralTypeIssues]

    class LooseState(rx.State):
        @rx.event
        def on_submit(self, form_data: LooseData):
            pass

    with pytest.raises(EventHandlerValueError, match=r"typing_extensions\.TypedDict"):
        HTMLForm.create(
            Input.create(name="tags"),
            id="loose",
            on_submit=LooseState.on_submit,
        )


class _SubmitState(rx.State):
    @rx.event
    def on_submit(self, form_data: dict):
        pass


def test_on_submit_warns_for_controls_with_only_an_id(caplog):
    """A control with a static id but no name is no longer submitted, so warn."""
    with caplog.at_level(logging.WARNING):
        HTMLForm.create(
            Input.create(id="only_id_input"),
            rx.checkbox(id="only_id_checkbox"),
            on_submit=_SubmitState.on_submit,
        )
    assert "only_id_input" in caplog.text
    assert "only_id_checkbox" in caplog.text
    assert "`name`" in caplog.text


@pytest.mark.parametrize(
    "control",
    [
        lambda: Input.create(id="named_input", name="named_input"),
        lambda: Input.create(id="submit_input", type="submit"),
        lambda: Input.create(id=Var(_js_expr="dynamic_id", _var_type=str)),
        lambda: rx.button("Submit", id="submit_button"),
    ],
)
def test_on_submit_does_not_warn_for_submitted_or_valueless_controls(control, caplog):
    """Named controls, buttons and dynamic ids need no warning."""
    with caplog.at_level(logging.WARNING):
        HTMLForm.create(control(), on_submit=_SubmitState.on_submit)
    assert "`name`" not in caplog.text


def test_form_without_form_data_handler_does_not_warn(caplog):
    """A form whose submit handler takes no form data has nothing to miss."""
    with caplog.at_level(logging.WARNING):
        HTMLForm.create(Input.create(id="unsubmitted_input"))
    assert "unsubmitted_input" not in caplog.text


def test_on_submit_typed_dict_ignores_dynamic_ids():
    """A dynamic id cannot contribute a form_data key, so validation still runs."""

    class SignupData(TypedDict):
        email: str

    class SignupState(rx.State):
        @rx.event
        def on_submit(self, form_data: SignupData):
            pass

    with pytest.raises(EventHandlerValueError):
        HTMLForm.create(
            Input.create(id=Var(_js_expr="dynamic_id", _var_type=str)),
            on_submit=SignupState.on_submit,
        )


@pytest.mark.parametrize("form_factory", [HTMLForm.create, Form.create])
def test_on_submit_collects_form_data_by_name_only(form_factory):
    """The submit handler reads FormData by name and never reads id refs."""
    form = form_factory(
        Input.create(id="email_input", name="email"),
        on_submit=Var(_js_expr="submit_it", _var_type=EventChain),
    )
    (hook,) = form.add_hooks()
    assert "const form_data = getFormData($form);" in hook
    assert "ref_email_input" not in hook
    assert "getRefValue" not in hook


def test_on_submit_accepts_typed_dict_with_optional_fields():
    """Optional TypedDict keys should not be required in the form."""

    class SignupData(TypedDict):
        email: str
        nickname: NotRequired[str]

    class SignupState(rx.State):
        @rx.event
        def on_submit(self, form_data: SignupData):
            pass

    # RED: without NotRequired handling, nickname would be treated as required
    # and the form below (which only has "email") would raise.
    form = HTMLForm.create(
        Input.create(name="email"),
        on_submit=SignupState.on_submit,
    )
    assert isinstance(form.event_triggers["on_submit"], EventChain)

    # Prove validation is active: a truly missing required field still raises.
    class StrictData(TypedDict):
        email: str
        nickname: str

    class StrictState(rx.State):
        @rx.event
        def on_submit(self, form_data: StrictData):
            pass

    with pytest.raises(EventHandlerValueError):
        HTMLForm.create(
            Input.create(name="email"),
            on_submit=StrictState.on_submit,
        )


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


def test_on_submit_accepts_typed_dict_with_inherited_optional_fields():
    """Inherited optional TypedDict keys should remain optional."""

    class BaseSignupData(TypedDict, total=False):
        nickname: str

    class SignupData(BaseSignupData):
        email: str

    class SignupState(rx.State):
        @rx.event
        def on_submit(self, form_data: SignupData):
            pass

    # RED: without proper inheritance handling, nickname (from the total=False
    # parent) would be treated as required, and this form would raise.
    form = HTMLForm.create(
        Input.create(name="email"),
        on_submit=SignupState.on_submit,
    )
    assert isinstance(form.event_triggers["on_submit"], EventChain)

    # Prove the inherited field IS accepted when provided.
    form_with_both = HTMLForm.create(
        Input.create(name="email"),
        Input.create(name="nickname"),
        on_submit=SignupState.on_submit,
    )
    assert isinstance(form_with_both.event_triggers["on_submit"], EventChain)


@pytest.mark.parametrize(
    "annotation",
    [FormData, FormData[str, Any], FormData[str, str], rx.form.FormData],
)
@pytest.mark.parametrize("form_factory", [HTMLForm.create, Form.create])
def test_on_submit_accepts_form_data_annotation(form_factory, annotation, caplog):
    """FormData-annotated submit handlers are accepted without a mismatch warning."""

    class TagsState(rx.State):
        @rx.event
        def on_submit(self, form_data: annotation):  # pyright: ignore[reportInvalidTypeForm]
            pass

    with caplog.at_level(logging.WARNING):
        form = form_factory(
            Input.create(name="tag"),
            on_submit=TagsState.on_submit,
        )

    assert isinstance(form.event_triggers["on_submit"], EventChain)
    assert "intentionally ignored" not in caplog.text


@pytest.mark.parametrize(
    "control",
    [
        lambda: rx.checkbox("Subscribe", name="subscribe"),
        lambda: rx.switch(name="subscribe"),
        lambda: Input.create(type="checkbox", name="subscribe"),
    ],
)
def test_on_submit_typed_dict_bool_field_accepts_toggle_controls(control):
    """Checkboxes and switches satisfy a required TypedDict bool field."""

    class PrefsData(TypedDict):
        subscribe: bool

    class PrefsState(rx.State):
        @rx.event
        def on_submit(self, form_data: PrefsData):
            pass

    form = HTMLForm.create(control(), on_submit=PrefsState.on_submit)
    assert isinstance(form.event_triggers["on_submit"], EventChain)


def test_form_data_is_exported_on_the_form_namespace():
    """Apps annotate form data with rx.form.FormData."""
    assert rx.form.FormData is FormData


def test_on_submit_rejects_non_mapping_form_data():
    """A non-mapping annotation is a type mismatch, not a failed comparison."""

    class TagsState(rx.State):
        @rx.event
        def on_submit(self, form_data: list[str]):
            pass

    with pytest.raises(EventHandlerArgTypeMismatchError):
        HTMLForm.create(on_submit=TagsState.on_submit)  # pyright: ignore[reportArgumentType]


def test_on_submit_accepts_controls_associated_via_form_attribute():
    """Controls associated via the HTML form attribute should not fail validation."""

    class SignupData(TypedDict):
        email: str

    class SignupState(rx.State):
        @rx.event
        def on_submit(self, form_data: SignupData):
            pass

    # RED: without the form-id escape hatch, this would raise
    # EventHandlerValueError because the form has no child inputs
    # matching the TypedDict's required "email" field.
    # (The input is associated externally via form="signup".)
    form = HTMLForm.create(
        id="signup",
        on_submit=SignupState.on_submit,
    )
    Input.create(name="email", form="signup")

    assert isinstance(form.event_triggers["on_submit"], EventChain)

    # Verify it WOULD fail without the id (proving the escape hatch matters).
    with pytest.raises(EventHandlerValueError):
        HTMLForm.create(
            on_submit=SignupState.on_submit,
        )


def test_on_submit_typed_dict_skips_dynamic_field_identifiers():
    """Dynamic field names should skip strict validation instead of raising."""

    class SignupData(TypedDict):
        email: str

    class SignupState(rx.State):
        @rx.event
        def on_submit(self, form_data: SignupData):
            pass

    # RED: without the dynamic-field escape hatch, this would raise
    # because "email" isn't statically present.  The dynamic Var name
    # could resolve to "email" at runtime, so validation must be skipped.
    form = HTMLForm.create(
        Input.create(name=Var(_js_expr="dynamic_name", _var_type=str)),
        on_submit=SignupState.on_submit,
    )

    assert isinstance(form.event_triggers["on_submit"], EventChain)

    # Verify it WOULD fail with a static non-matching name.
    with pytest.raises(EventHandlerValueError):
        HTMLForm.create(
            Input.create(name="wrong_field"),
            on_submit=SignupState.on_submit,
        )


def test_textarea_enter_key_submit_emits_helper():
    """`enter_key_submit=True` must inject the onKeyDown helper into the page."""
    ta = Textarea.create(enter_key_submit=True)
    assert ENTER_KEY_SUBMIT_JS in _root_only_custom_code(ta)


def test_textarea_auto_height_emits_helper():
    """`auto_height=True` must inject the onInput helper into the page."""
    ta = Textarea.create(auto_height=True)
    assert AUTO_HEIGHT_JS in _root_only_custom_code(ta)


def test_textarea_without_features_emits_no_helpers():
    """A bare textarea should not pull in either helper snippet."""
    collected = _root_only_custom_code(Textarea.create())
    assert ENTER_KEY_SUBMIT_JS not in collected
    assert AUTO_HEIGHT_JS not in collected


def test_form_message_force_match_requires_match():
    """force_match is only rendered when match is set, since Radix ignores it otherwise."""
    props = FormMessage.create("msg", name="field", force_match=True).render()["props"]
    assert not any(prop.startswith("forceMatch") for prop in props)

    props = FormMessage.create(
        "msg", name="field", match="valueMissing", force_match=True
    ).render()["props"]
    assert "forceMatch:true" in props
