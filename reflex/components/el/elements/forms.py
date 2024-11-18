"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""

from __future__ import annotations

from hashlib import md5
from typing import Any, Dict, Iterator, Set, Tuple, Union

from jinja2 import Environment

from reflex.components.el.element import Element
from reflex.components.tags.tag import Tag
from reflex.constants import Dirs, EventTriggers
from reflex.event import (
    EventChain,
    EventHandler,
    input_event,
    key_event,
    prevent_default,
)
from reflex.utils.imports import ImportDict
from reflex.vars import VarData
from reflex.vars.base import LiteralVar, Var

from .base import BaseHTML

FORM_DATA = Var(_js_expr="form_data")
HANDLE_SUBMIT_JS_JINJA2 = Environment().from_string(
    """
    const handleSubmit_{{ handle_submit_unique_name }} = useCallback((ev) => {
        const $form = ev.target
        ev.preventDefault()
        const {{ form_data }} = {...Object.fromEntries(new FormData($form).entries()), ...{{ field_ref_mapping }}};

        ({{ on_submit_event_chain }}());

        if ({{ reset_on_submit }}) {
            $form.reset()
        }
    })
    """
)


class Button(BaseHTML):
    """Display the button element."""

    tag = "button"

    # Automatically focuses the button when the page loads
    auto_focus: Var[Union[str, int, bool]]

    # Disables the button
    disabled: Var[bool]

    # Associates the button with a form (by id)
    form: Var[Union[str, int, bool]]

    # URL to send the form data to (for type="submit" buttons)
    form_action: Var[Union[str, int, bool]]

    # How the form data should be encoded when submitting to the server (for type="submit" buttons)
    form_enc_type: Var[Union[str, int, bool]]

    # HTTP method to use for sending form data (for type="submit" buttons)
    form_method: Var[Union[str, int, bool]]

    # Bypasses form validation when submitting (for type="submit" buttons)
    form_no_validate: Var[Union[str, int, bool]]

    # Specifies where to display the response after submitting the form (for type="submit" buttons)
    form_target: Var[Union[str, int, bool]]

    # Name of the button, used when sending form data
    name: Var[Union[str, int, bool]]

    # Type of the button (submit, reset, or button)
    type: Var[Union[str, int, bool]]

    # Value of the button, used when sending form data
    value: Var[Union[str, int, bool]]


class Datalist(BaseHTML):
    """Display the datalist element."""

    tag = "datalist"
    # No unique attributes, only common ones are inherited


class Fieldset(Element):
    """Display the fieldset element."""

    tag = "fieldset"

    # Disables all the form control descendants of the fieldset
    disabled: Var[Union[str, int, bool]]

    # Associates the fieldset with a form (by id)
    form: Var[Union[str, int, bool]]

    # Name of the fieldset, used for scripting
    name: Var[Union[str, int, bool]]


def on_submit_event_spec() -> Tuple[Var[Dict[str, Any]]]:
    """Event handler spec for the on_submit event.

    Returns:
        The event handler spec.
    """
    return (FORM_DATA,)


def on_submit_string_event_spec() -> Tuple[Var[Dict[str, str]]]:
    """Event handler spec for the on_submit event.

    Returns:
        The event handler spec.
    """
    return (FORM_DATA,)


class Form(BaseHTML):
    """Display the form element."""

    tag = "form"

    # MIME types the server accepts for file upload
    accept: Var[Union[str, int, bool]]

    # Character encodings to be used for form submission
    accept_charset: Var[Union[str, int, bool]]

    # URL where the form's data should be submitted
    action: Var[Union[str, int, bool]]

    # Whether the form should have autocomplete enabled
    auto_complete: Var[Union[str, int, bool]]

    # Encoding type for the form data when submitted
    enc_type: Var[Union[str, int, bool]]

    # HTTP method to use for form submission
    method: Var[Union[str, int, bool]]

    # Name of the form
    name: Var[Union[str, int, bool]]

    # Indicates that the form should not be validated on submit
    no_validate: Var[Union[str, int, bool]]

    # Where to display the response after submitting the form
    target: Var[Union[str, int, bool]]

    # If true, the form will be cleared after submit.
    reset_on_submit: Var[bool] = False  # type: ignore

    # The name used to make this form's submit handler function unique.
    handle_submit_unique_name: Var[str]

    # Fired when the form is submitted
    on_submit: EventHandler[on_submit_event_spec, on_submit_string_event_spec]

    @classmethod
    def create(cls, *children, **props):
        """Create a form component.

        Args:
            *children: The children of the form.
            **props: The properties of the form.

        Returns:
            The form component.
        """
        if "on_submit" not in props:
            props["on_submit"] = prevent_default

        if "handle_submit_unique_name" in props:
            return super().create(*children, **props)

        # Render the form hooks and use the hash of the resulting code to create a unique name.
        props["handle_submit_unique_name"] = ""
        form = super().create(*children, **props)
        form.handle_submit_unique_name = md5(
            str({**form._get_all_hooks_internal(), **form._get_all_hooks()}).encode(
                "utf-8"
            )
        ).hexdigest()
        return form

    def add_imports(self) -> ImportDict:
        """Add imports needed by the form component.

        Returns:
            The imports for the form component.
        """
        return {
            "react": "useCallback",
            f"$/{Dirs.STATE_PATH}": ["getRefValue", "getRefValues"],
        }

    def add_hooks(self) -> list[str]:
        """Add hooks for the form.

        Returns:
            The hooks for the form.
        """
        if EventTriggers.ON_SUBMIT not in self.event_triggers:
            return []
        return [
            HANDLE_SUBMIT_JS_JINJA2.render(
                handle_submit_unique_name=self.handle_submit_unique_name,
                form_data=FORM_DATA,
                field_ref_mapping=str(LiteralVar.create(self._get_form_refs())),
                on_submit_event_chain=str(
                    LiteralVar.create(self.event_triggers[EventTriggers.ON_SUBMIT])
                ),
                reset_on_submit=self.reset_on_submit,
            )
        ]

    def _render(self) -> Tag:
        render_tag = super()._render()
        if EventTriggers.ON_SUBMIT in self.event_triggers:
            render_tag.add_props(
                **{
                    EventTriggers.ON_SUBMIT: Var(
                        _js_expr=f"handleSubmit_{self.handle_submit_unique_name}",
                        _var_type=EventChain,
                    )
                }
            )
        return render_tag

    def _get_form_refs(self) -> Dict[str, Any]:
        # Send all the input refs to the handler.
        form_refs = {}
        for ref in self._get_all_refs():
            # when ref start with refs_ it's an array of refs, so we need different method
            # to collect data
            if ref.startswith("refs_"):
                ref_var = Var(_js_expr=ref[:-3])._as_ref()
                form_refs[ref[len("refs_") : -3]] = Var(
                    _js_expr=f"getRefValues({str(ref_var)})",
                    _var_data=VarData.merge(ref_var._get_all_var_data()),
                )
            else:
                ref_var = Var(_js_expr=ref)._as_ref()
                form_refs[ref[4:]] = Var(
                    _js_expr=f"getRefValue({str(ref_var)})",
                    _var_data=VarData.merge(ref_var._get_all_var_data()),
                )
        # print(repr(form_refs))
        return form_refs

    def _get_vars(self, include_children: bool = True) -> Iterator[Var]:
        yield from super()._get_vars(include_children=include_children)
        yield from self._get_form_refs().values()

    def _exclude_props(self) -> list[str]:
        return super()._exclude_props() + [
            "reset_on_submit",
            "handle_submit_unique_name",
        ]


class Input(BaseHTML):
    """Display the input element."""

    tag = "input"

    # Accepted types of files when the input is file type
    accept: Var[Union[str, int, bool]]

    # Alternate text for input type="image"
    alt: Var[Union[str, int, bool]]

    # Whether the input should have autocomplete enabled
    auto_complete: Var[Union[str, int, bool]]

    # Automatically focuses the input when the page loads
    auto_focus: Var[Union[str, int, bool]]

    # Captures media from the user (camera or microphone)
    capture: Var[Union[str, int, bool]]

    # Indicates whether the input is checked (for checkboxes and radio buttons)
    checked: Var[Union[str, int, bool]]

    # The initial value (for checkboxes and radio buttons)
    default_checked: Var[bool]

    # The initial value for a text field
    default_value: Var[str]

    # Name part of the input to submit in 'dir' and 'name' pair when form is submitted
    dirname: Var[Union[str, int, bool]]

    # Disables the input
    disabled: Var[Union[str, int, bool]]

    # Associates the input with a form (by id)
    form: Var[Union[str, int, bool]]

    # URL to send the form data to (for type="submit" buttons)
    form_action: Var[Union[str, int, bool]]

    # How the form data should be encoded when submitting to the server (for type="submit" buttons)
    form_enc_type: Var[Union[str, int, bool]]

    # HTTP method to use for sending form data (for type="submit" buttons)
    form_method: Var[Union[str, int, bool]]

    # Bypasses form validation when submitting (for type="submit" buttons)
    form_no_validate: Var[Union[str, int, bool]]

    # Specifies where to display the response after submitting the form (for type="submit" buttons)
    form_target: Var[Union[str, int, bool]]

    # References a datalist for suggested options
    list: Var[Union[str, int, bool]]

    # Specifies the maximum value for the input
    max: Var[Union[str, int, bool]]

    # Specifies the maximum number of characters allowed in the input
    max_length: Var[Union[str, int, bool]]

    # Specifies the minimum number of characters required in the input
    min_length: Var[Union[str, int, bool]]

    # Specifies the minimum value for the input
    min: Var[Union[str, int, bool]]

    # Indicates whether multiple values can be entered in an input of the type email or file
    multiple: Var[Union[str, int, bool]]

    # Name of the input, used when sending form data
    name: Var[Union[str, int, bool]]

    # Regex pattern the input's value must match to be valid
    pattern: Var[Union[str, int, bool]]

    # Placeholder text in the input
    placeholder: Var[Union[str, int, bool]]

    # Indicates whether the input is read-only
    read_only: Var[Union[str, int, bool]]

    # Indicates that the input is required
    required: Var[Union[str, int, bool]]

    # Specifies the visible width of a text control
    size: Var[Union[str, int, bool]]

    # URL for image inputs
    src: Var[Union[str, int, bool]]

    # Specifies the legal number intervals for an input
    step: Var[Union[str, int, bool]]

    # Specifies the type of input
    type: Var[Union[str, int, bool]]

    # Name of the image map used with the input
    use_map: Var[Union[str, int, bool]]

    # Value of the input
    value: Var[Union[str, int, float]]

    # Fired when the input value changes
    on_change: EventHandler[input_event]

    # Fired when the input gains focus
    on_focus: EventHandler[input_event]

    # Fired when the input loses focus
    on_blur: EventHandler[input_event]

    # Fired when a key is pressed down
    on_key_down: EventHandler[key_event]

    # Fired when a key is released
    on_key_up: EventHandler[key_event]


class Label(BaseHTML):
    """Display the label element."""

    tag = "label"

    # ID of a form control with which the label is associated
    html_for: Var[Union[str, int, bool]]

    # Associates the label with a form (by id)
    form: Var[Union[str, int, bool]]


class Legend(BaseHTML):
    """Display the legend element."""

    tag = "legend"
    # No unique attributes, only common ones are inherited


class Meter(BaseHTML):
    """Display the meter element."""

    tag = "meter"

    # Associates the meter with a form (by id)
    form: Var[Union[str, int, bool]]

    # High limit of range (above this is considered high value)
    high: Var[Union[str, int, bool]]

    # Low limit of range (below this is considered low value)
    low: Var[Union[str, int, bool]]

    # Maximum value of the range
    max: Var[Union[str, int, bool]]

    # Minimum value of the range
    min: Var[Union[str, int, bool]]

    # Optimum value in the range
    optimum: Var[Union[str, int, bool]]

    # Current value of the meter
    value: Var[Union[str, int, bool]]


class Optgroup(BaseHTML):
    """Display the optgroup element."""

    tag = "optgroup"

    # Disables the optgroup
    disabled: Var[Union[str, int, bool]]

    # Label for the optgroup
    label: Var[Union[str, int, bool]]


class Option(BaseHTML):
    """Display the option element."""

    tag = "option"

    # Disables the option
    disabled: Var[Union[str, int, bool]]

    # Label for the option, if the text is not the label
    label: Var[Union[str, int, bool]]

    # Indicates that the option is initially selected
    selected: Var[Union[str, int, bool]]

    # Value to be sent as form data
    value: Var[Union[str, int, bool]]


class Output(BaseHTML):
    """Display the output element."""

    tag = "output"

    # Associates the output with one or more elements (by their IDs)
    html_for: Var[Union[str, int, bool]]

    # Associates the output with a form (by id)
    form: Var[Union[str, int, bool]]

    # Name of the output element for form submission
    name: Var[Union[str, int, bool]]


class Progress(BaseHTML):
    """Display the progress element."""

    tag = "progress"

    # Associates the progress element with a form (by id)
    form: Var[Union[str, int, bool]]

    # Maximum value of the progress indicator
    max: Var[Union[str, int, bool]]

    # Current value of the progress indicator
    value: Var[Union[str, int, bool]]


class Select(BaseHTML):
    """Display the select element."""

    tag = "select"

    # Whether the form control should have autocomplete enabled
    auto_complete: Var[Union[str, int, bool]]

    # Automatically focuses the select when the page loads
    auto_focus: Var[Union[str, int, bool]]

    # Disables the select control
    disabled: Var[Union[str, int, bool]]

    # Associates the select with a form (by id)
    form: Var[Union[str, int, bool]]

    # Indicates that multiple options can be selected
    multiple: Var[Union[str, int, bool]]

    # Name of the select, used when submitting the form
    name: Var[Union[str, int, bool]]

    # Indicates that the select control must have a selected option
    required: Var[Union[str, int, bool]]

    # Number of visible options in a drop-down list
    size: Var[Union[str, int, bool]]

    # Fired when the select value changes
    on_change: EventHandler[input_event]


AUTO_HEIGHT_JS = """
const autoHeightOnInput = (e, is_enabled) => {
    if (is_enabled) {
        const el = e.target;
        el.style.overflowY = "scroll";
        el.style.height = "auto";
        el.style.height = (e.target.scrollHeight) + "px";
        if (el.form && !el.form.data_resize_on_reset) {
            el.form.addEventListener("reset", () => window.setTimeout(() => autoHeightOnInput(e, is_enabled), 0))
            el.form.data_resize_on_reset = true;
        }
    }
}
"""


ENTER_KEY_SUBMIT_JS = """
const enterKeySubmitOnKeyDown = (e, is_enabled) => {
    if (is_enabled && e.which === 13 && !e.shiftKey) {
        e.preventDefault();
        if (!e.repeat) {
            if (e.target.form) {
                e.target.form.requestSubmit();
            }
        }
    }
}
"""


class Textarea(BaseHTML):
    """Display the textarea element."""

    tag = "textarea"

    # Whether the form control should have autocomplete enabled
    auto_complete: Var[Union[str, int, bool]]

    # Automatically focuses the textarea when the page loads
    auto_focus: Var[Union[str, int, bool]]

    # Automatically fit the content height to the text (use min-height with this prop)
    auto_height: Var[bool]

    # Visible width of the text control, in average character widths
    cols: Var[Union[str, int, bool]]

    # Name part of the textarea to submit in 'dir' and 'name' pair when form is submitted
    dirname: Var[Union[str, int, bool]]

    # Disables the textarea
    disabled: Var[Union[str, int, bool]]

    # Enter key submits form (shift-enter adds new line)
    enter_key_submit: Var[bool]

    # Associates the textarea with a form (by id)
    form: Var[Union[str, int, bool]]

    # Maximum number of characters allowed in the textarea
    max_length: Var[Union[str, int, bool]]

    # Minimum number of characters required in the textarea
    min_length: Var[Union[str, int, bool]]

    # Name of the textarea, used when submitting the form
    name: Var[Union[str, int, bool]]

    # Placeholder text in the textarea
    placeholder: Var[Union[str, int, bool]]

    # Indicates whether the textarea is read-only
    read_only: Var[Union[str, int, bool]]

    # Indicates that the textarea is required
    required: Var[Union[str, int, bool]]

    # Visible number of lines in the text control
    rows: Var[Union[str, int, bool]]

    # The controlled value of the textarea, read only unless used with on_change
    value: Var[Union[str, int, bool]]

    # How the text in the textarea is to be wrapped when submitting the form
    wrap: Var[Union[str, int, bool]]

    # Fired when the input value changes
    on_change: EventHandler[input_event]

    # Fired when the input gains focus
    on_focus: EventHandler[input_event]

    # Fired when the input loses focus
    on_blur: EventHandler[input_event]

    # Fired when a key is pressed down
    on_key_down: EventHandler[key_event]

    # Fired when a key is released
    on_key_up: EventHandler[key_event]

    @classmethod
    def create(cls, *children, **props):
        """Create a textarea component.

        Args:
            *children: The children of the textarea.
            **props: The properties of the textarea.

        Returns:
            The textarea component.

        Raises:
            ValueError: when `enter_key_submit` is combined with `on_key_down`.
        """
        enter_key_submit = props.get("enter_key_submit")
        auto_height = props.get("auto_height")
        custom_attrs = props.setdefault("custom_attrs", {})

        if enter_key_submit is not None:
            enter_key_submit = Var.create(enter_key_submit)
            if "on_key_down" in props:
                raise ValueError(
                    "Cannot combine `enter_key_submit` with `on_key_down`.",
                )
            custom_attrs["on_key_down"] = Var(
                _js_expr=f"(e) => enterKeySubmitOnKeyDown(e, {str(enter_key_submit)})",
                _var_data=VarData.merge(enter_key_submit._get_all_var_data()),
            )
        if auto_height is not None:
            auto_height = Var.create(auto_height)
            custom_attrs["on_input"] = Var(
                _js_expr=f"(e) => autoHeightOnInput(e, {str(auto_height)})",
                _var_data=VarData.merge(auto_height._get_all_var_data()),
            )
        return super().create(*children, **props)

    def _exclude_props(self) -> list[str]:
        return super()._exclude_props() + [
            "auto_height",
            "enter_key_submit",
        ]

    def _get_all_custom_code(self) -> Set[str]:
        """Include the custom code for auto_height and enter_key_submit functionality.

        Returns:
            The custom code for the component.
        """
        custom_code = super()._get_all_custom_code()
        if self.auto_height is not None:
            custom_code.add(AUTO_HEIGHT_JS)
        if self.enter_key_submit is not None:
            custom_code.add(ENTER_KEY_SUBMIT_JS)
        return custom_code


button = Button.create
fieldset = Fieldset.create
form = Form.create
input = Input.create
label = Label.create
legend = Legend.create
meter = Meter.create
optgroup = Optgroup.create
option = Option.create
output = Output.create
progress = Progress.create
select = Select.create
textarea = Textarea.create
