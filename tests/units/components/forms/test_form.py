import logging
from typing import Any, NotRequired, TypedDict, TypeVar

import pytest
from reflex_base.components.component import Component
from reflex_base.event import EventChain, prevent_default
from reflex_base.utils.exceptions import (
    EventHandlerArgTypeMismatchError,
    EventHandlerValueError,
)
from reflex_base.utils.form import FormData
from reflex_base.vars.base import Var
from reflex_components_core.core.debounce import DebounceInput
from reflex_components_core.el.elements.base import BaseHTML
from reflex_components_core.el.elements.forms import (
    AUTO_HEIGHT_JS,
    ENTER_KEY_SUBMIT_JS,
    Input,
    Textarea,
)
from reflex_components_core.el.elements.forms import Form as HTMLForm
from reflex_components_radix.primitives.form import Form, FormMessage

import reflex as rx
from reflex.compiler.utils import _root_only_custom_code

_T = TypeVar("_T")

EMAIL_FIELD_ID = "email"
EMAIL_LABEL_ID = "email_label"
SUBMIT_BUTTON_ID = "submit_button"
INPUT_WRAPPER_ID = "input_wrapper"
FORM_ID = "form_id"
DEBOUNCED_INPUT_ID = "debounced_input"
MEMOIZED_INPUT_ID = "memoized_input"


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


def test_form_submit_preserves_null_control_values():
    """ID-backed form controls remain in the payload when their value is null."""

    class FormState(rx.State):
        @rx.event
        def on_submit(self, form_data: dict):
            pass

    form = HTMLForm.create(
        rx.box(
            Input.create(id=EMAIL_FIELD_ID),
            rx.text("Email", id=EMAIL_LABEL_ID),
            rx.button("Submit", id=SUBMIT_BUTTON_ID),
            id=INPUT_WRAPPER_ID,
        ),
        on_submit=FormState.on_submit,
        id=FORM_ID,
    )
    submit_hook = form.add_hooks()[0]
    assert "filter(([, value]) => value != null)" not in submit_hook
    assert f"ref_{EMAIL_FIELD_ID}" in submit_hook
    assert f"ref_{EMAIL_LABEL_ID}" not in submit_hook
    assert f"ref_{SUBMIT_BUTTON_ID}" not in submit_hook
    assert f"ref_{INPUT_WRAPPER_ID}" not in submit_hook
    assert f"ref_{FORM_ID}" not in submit_hook


@pytest.mark.parametrize("native_tag", ["input", "select", "textarea"])
def test_form_refs_include_custom_native_controls(native_tag):
    """Custom native input elements with IDs are included in form data."""

    class NativeInput(BaseHTML):
        tag = native_tag

    form = HTMLForm.create(NativeInput.create(id="native_input"))

    assert "ref_native_input" in form.add_hooks()[0]


def test_form_refs_follow_replaced_children():
    """Replacing form children must not retain refs from the previous subtree."""
    form = HTMLForm.create(Input.create(id="original"))
    assert 'getRefValue(refs["ref_original"])' in form.add_hooks()[0]

    form.children = [Input.create(id="replacement")]

    hook = form.add_hooks()[0]
    assert 'getRefValue(refs["ref_replacement"])' in hook
    assert 'getRefValue(refs["ref_original"])' not in hook


def test_form_refs_include_opted_in_custom_controls():
    """Custom wrapped controls can opt in to ID-based form data."""

    class CustomControl(rx.Component):
        tag = "CustomControl"
        _is_form_control = True

    form = HTMLForm.create(CustomControl.create(id="custom_control"))

    assert "ref_custom_control" in form.add_hooks()[0]


def test_form_refs_include_debounced_controls():
    """ID-only debounced inputs remain available to submit handlers."""
    form = HTMLForm.create(
        DebounceInput.create(
            Input.create(id=DEBOUNCED_INPUT_ID, on_change=rx.console_log)
        )
    )

    assert f"ref_{DEBOUNCED_INPUT_ID}" in form.add_hooks()[0]


def test_form_refs_include_memoized_controls(monkeypatch):
    """Memo wrappers retain the form-control marker of their wrapped component."""

    class MemoizedInput(Input):
        _is_form_control = False

    monkeypatch.setattr(MemoizedInput, "_wrapped_component_type", Input, raising=False)
    form = HTMLForm.create(MemoizedInput.create(id=MEMOIZED_INPUT_ID))

    assert f"ref_{MEMOIZED_INPUT_ID}" in form.add_hooks()[0]


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
    """Submitting a control with a static id but no name by its id is deprecated."""
    with caplog.at_level(logging.WARNING):
        HTMLForm.create(
            Input.create(id="only_id_input"),
            rx.checkbox(id="only_id_checkbox"),
            on_submit=_SubmitState.on_submit,
        )
    assert "only_id_input" in caplog.text
    assert "only_id_checkbox" in caplog.text
    assert "`name`" in caplog.text


def _native_control(tag: str) -> Component:
    """Create a custom component rendering a native form control.

    Args:
        tag: The native element.

    Returns:
        The component, with an id but no name.
    """

    class NativeControl(BaseHTML):
        pass

    NativeControl.tag = tag
    return NativeControl.create(id=f"native_{tag}")


def _opted_in_control() -> Component:
    """Create a custom component that opts in as a form control.

    Returns:
        The component, with an id but no name.
    """

    class CustomControl(rx.Component):
        tag = "CustomControl"
        _is_form_control = True

    return CustomControl.create(id="custom_control")


def _memoized_control() -> Component:
    """Create a component whose memoized type is a form control.

    Returns:
        The component, with an id but no name.
    """

    class MemoizedInput(Input):
        _is_form_control = False
        _wrapped_component_type = Input

    return MemoizedInput.create(id="memoized_input")


@pytest.mark.parametrize(
    ("control", "control_id"),
    [
        (lambda: _native_control("input"), "native_input"),
        (lambda: _native_control("select"), "native_select"),
        (lambda: _native_control("textarea"), "native_textarea"),
        (_opted_in_control, "custom_control"),
        (_memoized_control, "memoized_input"),
        (
            lambda: DebounceInput.create(
                Input.create(id="debounced_input", on_change=rx.console_log)
            ),
            "debounced_input",
        ),
    ],
)
def test_on_submit_warns_for_custom_controls_with_only_an_id(
    control, control_id, caplog
):
    """Custom, memoized and debounced controls count as form controls."""
    with caplog.at_level(logging.WARNING):
        HTMLForm.create(control(), on_submit=_SubmitState.on_submit)
    assert repr(control_id) in caplog.text


@pytest.mark.parametrize(
    "control",
    [
        lambda: Input.create(id="named_input", name="named_input"),
        lambda: Input.create(id="submit_input", type="submit"),
        lambda: Input.create(id=Var(_js_expr="dynamic_id", _var_type=str)),
        lambda: rx.button("Submit", id="submit_button"),
        lambda: rx.text("Email", id="email_label"),
        lambda: rx.box(Input.create(name="wrapped_input"), id="input_wrapper"),
        lambda: Input.create(id="disabled_input", disabled=True),
    ],
)
def test_on_submit_does_not_warn_for_submitted_or_valueless_controls(control, caplog):
    """Named, disabled and value-less controls and dynamic ids need no warning."""
    with caplog.at_level(logging.WARNING):
        HTMLForm.create(control(), on_submit=_SubmitState.on_submit)
    assert "`name`" not in caplog.text


def test_form_without_form_data_handler_does_not_warn(caplog):
    """A form whose submit handler takes no form data has nothing to miss."""
    with caplog.at_level(logging.WARNING):
        HTMLForm.create(Input.create(id="unsubmitted_input"))
    assert "unsubmitted_input" not in caplog.text


def test_on_submit_accepts_typed_dict_with_unresolvable_field_types():
    """A field type that cannot be resolved, as under TYPE_CHECKING, still compiles."""

    class OrderData(TypedDict):
        name: str
        amount: "Decimal"  # noqa: F821 # pyright: ignore[reportUndefinedVariable]
        tip: "NotRequired[Decimal]"  # noqa: F821 # pyright: ignore[reportUndefinedVariable]
        fee: "NotRequired[billing.Money]"  # noqa: F821 # pyright: ignore[reportUndefinedVariable]

    class OrderState(rx.State):
        @rx.event
        def on_submit(self, form_data: OrderData):
            pass

    HTMLForm.create(
        Input.create(name="name"),
        Input.create(name="amount"),
        on_submit=OrderState.on_submit,
    )
    with pytest.raises(EventHandlerValueError, match="amount"):
        HTMLForm.create(Input.create(name="name"), on_submit=OrderState.on_submit)


@pytest.mark.parametrize("form_factory", [HTMLForm.create, Form.create])
def test_on_submit_collects_form_data_with_id_refs(form_factory):
    """The submit handler reads FormData, passing the values of id refs to replace it."""
    form = form_factory(
        Input.create(id="email_input", name="email"),
        on_submit=Var(_js_expr="submit_it", _var_type=EventChain),
    )
    (hook,) = form.add_hooks()
    assert (
        "const form_data = getFormData($form, "
        '({ ["email_input"] : getRefValue(refs["ref_email_input"]) }));'
    ) in hook


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


def test_on_submit_typed_dict_list_field_accepts_bracketed_control_name():
    """A required list field is filled by controls named ``name[]``."""

    class TagsData(TypedDict):
        tags: list[str]
        pick: str

    class TagsState(rx.State):
        @rx.event
        def on_submit(self, form_data: TagsData):
            pass

    HTMLForm.create(
        Input.create(name="tags[]"),
        Input.create(name="pick"),
        on_submit=TagsState.on_submit,
    )
    # Only a list field takes the bracketed name.
    with pytest.raises(EventHandlerValueError, match="pick"):
        HTMLForm.create(
            Input.create(name="tags"),
            Input.create(name="pick[]"),
            on_submit=TagsState.on_submit,
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
    [
        FormData,
        FormData[str, Any],
        FormData[str, str],
        FormData[str, str] | None,
        rx.form.FormData,
    ],
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
