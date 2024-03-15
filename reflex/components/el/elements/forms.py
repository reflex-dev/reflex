"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from __future__ import annotations

from hashlib import md5
from typing import Any, Dict, Iterator, Union

from jinja2 import Environment

from reflex.components.el.element import Element
from reflex.components.tags.tag import Tag
from reflex.constants import Dirs, EventTriggers
from reflex.event import EventChain
from reflex.utils import imports
from reflex.utils.format import format_event_chain
from reflex.vars import BaseVar, Var

from .base import BaseHTML

FORM_DATA = Var.create("form_data")
HANDLE_SUBMIT_JS_JINJA2 = Environment().from_string(
    """
    const handleSubmit_{{ handle_submit_unique_name }} = useCallback((ev) => {
        const $form = ev.target
        ev.preventDefault()
        const {{ form_data }} = {...Object.fromEntries(new FormData($form).entries()), ...{{ field_ref_mapping }}}

        {{ on_submit_event_chain }}

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

    def get_event_triggers(self) -> Dict[str, Any]:
        """Event triggers for radix form root.

        Returns:
            The triggers for event supported by Root.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_SUBMIT: lambda e0: [FORM_DATA],
        }

    @classmethod
    def create(cls, *children, **props):
        """Create a form component.

        Args:
            *children: The children of the form.
            **props: The properties of the form.

        Returns:
            The form component.
        """
        if "handle_submit_unique_name" in props:
            return super().create(*children, **props)

        # Render the form hooks and use the hash of the resulting code to create a unique name.
        props["handle_submit_unique_name"] = ""
        form = super().create(*children, **props)
        form.handle_submit_unique_name = md5(
            str(form.get_hooks_internal().union(form.get_hooks())).encode("utf-8")
        ).hexdigest()
        return form

    def _get_imports(self) -> imports.ImportDict:
        return imports.merge_imports(
            super()._get_imports(),
            {
                "react": {imports.ImportVar(tag="useCallback")},
                f"/{Dirs.STATE_PATH}": {
                    imports.ImportVar(tag="getRefValue"),
                    imports.ImportVar(tag="getRefValues"),
                },
            },
        )

    def _get_hooks(self) -> str | None:
        if EventTriggers.ON_SUBMIT not in self.event_triggers:
            return
        return HANDLE_SUBMIT_JS_JINJA2.render(
            handle_submit_unique_name=self.handle_submit_unique_name,
            form_data=FORM_DATA,
            field_ref_mapping=str(Var.create_safe(self._get_form_refs())),
            on_submit_event_chain=format_event_chain(
                self.event_triggers[EventTriggers.ON_SUBMIT]
            ),
            reset_on_submit=self.reset_on_submit,
        )

    def _render(self) -> Tag:
        render_tag = super()._render()
        if EventTriggers.ON_SUBMIT in self.event_triggers:
            render_tag.add_props(
                **{
                    EventTriggers.ON_SUBMIT: BaseVar(
                        _var_name=f"handleSubmit_{self.handle_submit_unique_name}",
                        _var_type=EventChain,
                    )
                }
            )
        return render_tag

    def _get_form_refs(self) -> Dict[str, Any]:
        # Send all the input refs to the handler.
        form_refs = {}
        for ref in self.get_refs():
            # when ref start with refs_ it's an array of refs, so we need different method
            # to collect data
            if ref.startswith("refs_"):
                ref_var = Var.create_safe(ref[:-3]).as_ref()
                form_refs[ref[5:-3]] = Var.create_safe(
                    f"getRefValues({str(ref_var)})", _var_is_local=False
                )._replace(merge_var_data=ref_var._var_data)
            else:
                ref_var = Var.create_safe(ref).as_ref()
                form_refs[ref[4:]] = Var.create_safe(
                    f"getRefValue({str(ref_var)})", _var_is_local=False
                )._replace(merge_var_data=ref_var._var_data)
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
    value: Var[Union[str, int, bool]]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: lambda e0: [e0.target.value],
            EventTriggers.ON_FOCUS: lambda e0: [e0.target.value],
            EventTriggers.ON_BLUR: lambda e0: [e0.target.value],
            EventTriggers.ON_KEY_DOWN: lambda e0: [e0.key],
            EventTriggers.ON_KEY_UP: lambda e0: [e0.key],
        }


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

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: lambda e0: [e0.target.value],
        }


class Textarea(BaseHTML):
    """Display the textarea element."""

    tag = "textarea"

    # Whether the form control should have autocomplete enabled
    auto_complete: Var[Union[str, int, bool]]

    # Automatically focuses the textarea when the page loads
    auto_focus: Var[Union[str, int, bool]]

    # Visible width of the text control, in average character widths
    cols: Var[Union[str, int, bool]]

    # Name part of the textarea to submit in 'dir' and 'name' pair when form is submitted
    dirname: Var[Union[str, int, bool]]

    # Disables the textarea
    disabled: Var[Union[str, int, bool]]

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

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: lambda e0: [e0.target.value],
            EventTriggers.ON_FOCUS: lambda e0: [e0.target.value],
            EventTriggers.ON_BLUR: lambda e0: [e0.target.value],
            EventTriggers.ON_KEY_DOWN: lambda e0: [e0.key],
            EventTriggers.ON_KEY_UP: lambda e0: [e0.key],
        }
