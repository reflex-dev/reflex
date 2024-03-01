"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Any, Dict, Optional, Union

from reflex.components.el.element import Element
from reflex.constants.event import EventTriggers
from reflex.vars import Var

from .base import BaseHTML


class Button(BaseHTML):
    """Display the button element."""

    tag: str = "button"

    # Automatically focuses the button when the page loads
    auto_focus: Optional[Var[Union[str, int, bool]]] = None

    # Disables the button
    disabled: Optional[Var[bool]] = None

    # Associates the button with a form (by id)
    form: Optional[Var[Union[str, int, bool]]] = None

    # URL to send the form data to (for type="submit" buttons)
    form_action: Optional[Var[Union[str, int, bool]]] = None

    # How the form data should be encoded when submitting to the server (for type="submit" buttons)
    form_enc_type: Optional[Var[Union[str, int, bool]]] = None

    # HTTP method to use for sending form data (for type="submit" buttons)
    form_method: Optional[Var[Union[str, int, bool]]] = None

    # Bypasses form validation when submitting (for type="submit" buttons)
    form_no_validate: Optional[Var[Union[str, int, bool]]] = None

    # Specifies where to display the response after submitting the form (for type="submit" buttons)
    form_target: Optional[Var[Union[str, int, bool]]] = None

    # Name of the button, used when sending form data
    name: Optional[Var[Union[str, int, bool]]] = None

    # Type of the button (submit, reset, or button)
    type: Optional[Var[Union[str, int, bool]]] = None

    # Value of the button, used when sending form data
    value: Optional[Var[Union[str, int, bool]]] = None


class Datalist(BaseHTML):
    """Display the datalist element."""

    tag: str = "datalist"
    # No unique attributes, only common ones are inherited


class Fieldset(Element):
    """Display the fieldset element."""

    tag: str = "fieldset"

    # Disables all the form control descendants of the fieldset
    disabled: Optional[Var[Union[str, int, bool]]] = None

    # Associates the fieldset with a form (by id)
    form: Optional[Var[Union[str, int, bool]]] = None

    # Name of the fieldset, used for scripting
    name: Optional[Var[Union[str, int, bool]]] = None


class Form(BaseHTML):
    """Display the form element."""

    tag: str = "form"

    # MIME types the server accepts for file upload
    accept: Optional[Var[Union[str, int, bool]]] = None

    # Character encodings to be used for form submission
    accept_charset: Optional[Var[Union[str, int, bool]]] = None

    # URL where the form's data should be submitted
    action: Optional[Var[Union[str, int, bool]]] = None

    # Whether the form should have autocomplete enabled
    auto_complete: Optional[Var[Union[str, int, bool]]] = None

    # Encoding type for the form data when submitted
    enc_type: Optional[Var[Union[str, int, bool]]] = None

    # HTTP method to use for form submission
    method: Optional[Var[Union[str, int, bool]]] = None

    # Name of the form
    name: Optional[Var[Union[str, int, bool]]] = None

    # Indicates that the form should not be validated on submit
    no_validate: Optional[Var[Union[str, int, bool]]] = None

    # Where to display the response after submitting the form
    target: Optional[Var[Union[str, int, bool]]] = None


class Input(BaseHTML):
    """Display the input element."""

    tag: str = "input"

    # Accepted types of files when the input is file type
    accept: Optional[Var[Union[str, int, bool]]] = None

    # Alternate text for input type="image"
    alt: Optional[Var[Union[str, int, bool]]] = None

    # Whether the input should have autocomplete enabled
    auto_complete: Optional[Var[Union[str, int, bool]]] = None

    # Automatically focuses the input when the page loads
    auto_focus: Optional[Var[Union[str, int, bool]]] = None

    # Captures media from the user (camera or microphone)
    capture: Optional[Var[Union[str, int, bool]]] = None

    # Indicates whether the input is checked (for checkboxes and radio buttons)
    checked: Optional[Var[Union[str, int, bool]]] = None

    # The initial value (for checkboxes and radio buttons)
    default_checked: Optional[Var[bool]] = None

    # The initial value for a text field
    default_value: Optional[Var[str]] = None

    # Name part of the input to submit in 'dir' and 'name' pair when form is submitted
    dirname: Optional[Var[Union[str, int, bool]]] = None

    # Disables the input
    disabled: Optional[Var[Union[str, int, bool]]] = None

    # Associates the input with a form (by id)
    form: Optional[Var[Union[str, int, bool]]] = None

    # URL to send the form data to (for type="submit" buttons)
    form_action: Optional[Var[Union[str, int, bool]]] = None

    # How the form data should be encoded when submitting to the server (for type="submit" buttons)
    form_enc_type: Optional[Var[Union[str, int, bool]]] = None

    # HTTP method to use for sending form data (for type="submit" buttons)
    form_method: Optional[Var[Union[str, int, bool]]] = None

    # Bypasses form validation when submitting (for type="submit" buttons)
    form_no_validate: Optional[Var[Union[str, int, bool]]] = None

    # Specifies where to display the response after submitting the form (for type="submit" buttons)
    form_target: Optional[Var[Union[str, int, bool]]] = None

    # References a datalist for suggested options
    list: Optional[Var[Union[str, int, bool]]] = None

    # Specifies the maximum value for the input
    max: Optional[Var[Union[str, int, bool]]] = None

    # Specifies the maximum number of characters allowed in the input
    max_length: Optional[Var[Union[str, int, bool]]] = None

    # Specifies the minimum number of characters required in the input
    min_length: Optional[Var[Union[str, int, bool]]] = None

    # Specifies the minimum value for the input
    min: Optional[Var[Union[str, int, bool]]] = None

    # Indicates whether multiple values can be entered in an input of the type email or file
    multiple: Optional[Var[Union[str, int, bool]]] = None

    # Name of the input, used when sending form data
    name: Optional[Var[Union[str, int, bool]]] = None

    # Regex pattern the input's value must match to be valid
    pattern: Optional[Var[Union[str, int, bool]]] = None

    # Placeholder text in the input
    placeholder: Optional[Var[Union[str, int, bool]]] = None

    # Indicates whether the input is read-only
    read_only: Optional[Var[Union[str, int, bool]]] = None

    # Indicates that the input is required
    required: Optional[Var[Union[str, int, bool]]] = None

    # Specifies the visible width of a text control
    size: Optional[Var[Union[str, int, bool]]] = None

    # URL for image inputs
    src: Optional[Var[Union[str, int, bool]]] = None

    # Specifies the legal number intervals for an input
    step: Optional[Var[Union[str, int, bool]]] = None

    # Specifies the type of input
    type: Optional[Var[Union[str, int, bool]]] = None

    # Name of the image map used with the input
    use_map: Optional[Var[Union[str, int, bool]]] = None

    # Value of the input
    value: Optional[Var[Union[str, int, bool]]] = None

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

    tag: str = "label"

    # ID of a form control with which the label is associated
    html_for: Optional[Var[Union[str, int, bool]]] = None

    # Associates the label with a form (by id)
    form: Optional[Var[Union[str, int, bool]]] = None


class Legend(BaseHTML):
    """Display the legend element."""

    tag: str = "legend"
    # No unique attributes, only common ones are inherited


class Meter(BaseHTML):
    """Display the meter element."""

    tag: str = "meter"

    # Associates the meter with a form (by id)
    form: Optional[Var[Union[str, int, bool]]] = None

    # High limit of range (above this is considered high value)
    high: Optional[Var[Union[str, int, bool]]] = None

    # Low limit of range (below this is considered low value)
    low: Optional[Var[Union[str, int, bool]]] = None

    # Maximum value of the range
    max: Optional[Var[Union[str, int, bool]]] = None

    # Minimum value of the range
    min: Optional[Var[Union[str, int, bool]]] = None

    # Optimum value in the range
    optimum: Optional[Var[Union[str, int, bool]]] = None

    # Current value of the meter
    value: Optional[Var[Union[str, int, bool]]] = None


class Optgroup(BaseHTML):
    """Display the optgroup element."""

    tag: str = "optgroup"

    # Disables the optgroup
    disabled: Optional[Var[Union[str, int, bool]]] = None

    # Label for the optgroup
    label: Optional[Var[Union[str, int, bool]]] = None


class Option(BaseHTML):
    """Display the option element."""

    tag: str = "option"

    # Disables the option
    disabled: Optional[Var[Union[str, int, bool]]] = None

    # Label for the option, if the text is not the label
    label: Optional[Var[Union[str, int, bool]]] = None

    # Indicates that the option is initially selected
    selected: Optional[Var[Union[str, int, bool]]] = None

    # Value to be sent as form data
    value: Optional[Var[Union[str, int, bool]]] = None


class Output(BaseHTML):
    """Display the output element."""

    tag: str = "output"

    # Associates the output with one or more elements (by their IDs)
    html_for: Optional[Var[Union[str, int, bool]]] = None

    # Associates the output with a form (by id)
    form: Optional[Var[Union[str, int, bool]]] = None

    # Name of the output element for form submission
    name: Optional[Var[Union[str, int, bool]]] = None


class Progress(BaseHTML):
    """Display the progress element."""

    tag: str = "progress"

    # Associates the progress element with a form (by id)
    form: Optional[Var[Union[str, int, bool]]] = None

    # Maximum value of the progress indicator
    max: Optional[Var[Union[str, int, bool]]] = None

    # Current value of the progress indicator
    value: Optional[Var[Union[str, int, bool]]] = None


class Select(BaseHTML):
    """Display the select element."""

    tag: str = "select"

    # Whether the form control should have autocomplete enabled
    auto_complete: Optional[Var[Union[str, int, bool]]] = None

    # Automatically focuses the select when the page loads
    auto_focus: Optional[Var[Union[str, int, bool]]] = None

    # Disables the select control
    disabled: Optional[Var[Union[str, int, bool]]] = None

    # Associates the select with a form (by id)
    form: Optional[Var[Union[str, int, bool]]] = None

    # Indicates that multiple options can be selected
    multiple: Optional[Var[Union[str, int, bool]]] = None

    # Name of the select, used when submitting the form
    name: Optional[Var[Union[str, int, bool]]] = None

    # Indicates that the select control must have a selected option
    required: Optional[Var[Union[str, int, bool]]] = None

    # Number of visible options in a drop-down list
    size: Optional[Var[Union[str, int, bool]]] = None

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

    tag: str = "textarea"

    # Whether the form control should have autocomplete enabled
    auto_complete: Optional[Var[Union[str, int, bool]]] = None

    # Automatically focuses the textarea when the page loads
    auto_focus: Optional[Var[Union[str, int, bool]]] = None

    # Visible width of the text control, in average character widths
    cols: Optional[Var[Union[str, int, bool]]] = None

    # Name part of the textarea to submit in 'dir' and 'name' pair when form is submitted
    dirname: Optional[Var[Union[str, int, bool]]] = None

    # Disables the textarea
    disabled: Optional[Var[Union[str, int, bool]]] = None

    # Associates the textarea with a form (by id)
    form: Optional[Var[Union[str, int, bool]]] = None

    # Maximum number of characters allowed in the textarea
    max_length: Optional[Var[Union[str, int, bool]]] = None

    # Minimum number of characters required in the textarea
    min_length: Optional[Var[Union[str, int, bool]]] = None

    # Name of the textarea, used when submitting the form
    name: Optional[Var[Union[str, int, bool]]] = None

    # Placeholder text in the textarea
    placeholder: Optional[Var[Union[str, int, bool]]] = None

    # Indicates whether the textarea is read-only
    read_only: Optional[Var[Union[str, int, bool]]] = None

    # Indicates that the textarea is required
    required: Optional[Var[Union[str, int, bool]]] = None

    # Visible number of lines in the text control
    rows: Optional[Var[Union[str, int, bool]]] = None

    # The controlled value of the textarea, read only unless used with on_change
    value: Optional[Var[Union[str, int, bool]]] = None

    # How the text in the textarea is to be wrapped when submitting the form
    wrap: Optional[Var[Union[str, int, bool]]] = None

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
