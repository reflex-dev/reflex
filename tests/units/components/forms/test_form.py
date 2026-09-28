import json
import shutil
import subprocess
from typing import TypedDict

import pytest
from reflex_base.event import EventChain, prevent_default
from reflex_base.utils.exceptions import EventHandlerValueError
from reflex_base.vars.base import Var
from reflex_components_core.el.elements.forms import (
    AUTO_HEIGHT_JS,
    ENTER_KEY_SUBMIT_JS,
    FORM_DATA_TO_OBJECT_JS,
    Input,
    Textarea,
)
from reflex_components_core.el.elements.forms import Form as HTMLForm
from reflex_components_radix.primitives.form import Form, FormMessage
from typing_extensions import NotRequired

import reflex as rx
from reflex.compiler.utils import _root_only_custom_code


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


def test_on_submit_emits_form_data_to_object_helper():
    """A form with on_submit must inject the formDataToObject helper into the page."""
    f = HTMLForm.create(on_submit=prevent_default)
    assert FORM_DATA_TO_OBJECT_JS in _root_only_custom_code(f)


def test_handle_submit_uses_form_data_to_object_not_fromentries():
    """The submit hook must call formDataToObject, not Object.fromEntries(...entries()).

    Object.fromEntries silently collapses repeated FormData keys (e.g. a checkbox
    group) down to their last value, so any fix must route through the
    array-preserving formDataToObject helper instead.
    """
    f = HTMLForm.create(on_submit=prevent_default)
    hooks = "\n".join(f.add_hooks())
    assert "formDataToObject(new FormData($form))" in hooks
    assert "Object.fromEntries" not in hooks


# Runs FORM_DATA_TO_OBJECT_JS itself through node, so a regression in the actual
# grouping/prototype-safety logic is caught even if the surrounding hooks still
# reference the helper correctly. Mirrors the pattern in
# tests/units/reflex_base/templates/test_json_helper.py.
_FORM_DATA_TO_OBJECT_DRIVER = """
import { readFileSync } from "node:fs";
const helperSrc = readFileSync(process.argv[2], "utf8");
const formDataToObject = new Function(`${helperSrc}; return formDataToObject;`)();
const cases = JSON.parse(readFileSync(process.argv[3], "utf8"));
const results = cases.map((entries) => {
  const fd = new FormData();
  for (const [key, value] of entries) fd.append(key, value);
  return formDataToObject(fd);
});
process.stdout.write(JSON.stringify(results));
"""

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node missing")


@requires_node
def test_form_data_to_object_groups_repeated_keys_preserves_scalars(tmp_path):
    """The helper must group repeated keys into arrays and keep single
    keys as scalars, and must not corrupt keys that collide with
    Object.prototype members like "constructor" or "toString".

    Args:
        tmp_path: Pytest temporary directory.
    """
    helper_file = tmp_path / "helper.js"
    helper_file.write_text(FORM_DATA_TO_OBJECT_JS, encoding="utf-8")
    driver_file = tmp_path / "driver.mjs"
    driver_file.write_text(_FORM_DATA_TO_OBJECT_DRIVER, encoding="utf-8")
    cases_file = tmp_path / "cases.json"
    cases = [
        [["colors", "red"], ["colors", "green"], ["colors", "blue"], ["name", "bob"]],
        [["name", "bob"]],
        [["constructor", "a"], ["constructor", "b"], ["toString", "x"]],
    ]
    cases_file.write_text(json.dumps(cases), encoding="utf-8")

    result = subprocess.run(
        ["node", str(driver_file), str(helper_file), str(cases_file)],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    results = json.loads(result.stdout)

    assert results == [
        {"colors": ["red", "green", "blue"], "name": "bob"},
        {"name": "bob"},
        {"constructor": ["a", "b"], "toString": "x"},
    ]


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
