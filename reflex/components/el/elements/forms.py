"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Union

from reflex.components.el.element import Element
from reflex.vars import Var as Var_

from .base import BaseHTML


class Button(BaseHTML):
    """Display the button element."""

    tag = "button"

    # Automatically focuses the button when the page loads
    auto_focus: Var_[Union[str, int, bool]]

    # Disables the button
    disabled: Var_[Union[str, int, bool]]

    # Associates the button with a form (by id)
    form: Var_[Union[str, int, bool]]

    # URL to send the form data to (for type="submit" buttons)
    form_action: Var_[Union[str, int, bool]]

    # How the form data should be encoded when submitting to the server (for type="submit" buttons)
    form_enc_type: Var_[Union[str, int, bool]]

    # HTTP method to use for sending form data (for type="submit" buttons)
    form_method: Var_[Union[str, int, bool]]

    # Bypasses form validation when submitting (for type="submit" buttons)
    form_no_validate: Var_[Union[str, int, bool]]

    # Specifies where to display the response after submitting the form (for type="submit" buttons)
    form_target: Var_[Union[str, int, bool]]

    # Name of the button, used when sending form data
    name: Var_[Union[str, int, bool]]

    # Type of the button (submit, reset, or button)
    type: Var_[Union[str, int, bool]]

    # Value of the button, used when sending form data
    value: Var_[Union[str, int, bool]]


class Datalist(BaseHTML):
    """Display the datalist element."""

    tag = "datalist"
    # No unique attributes, only common ones are inherited


class Fieldset(Element):
    """Display the fieldset element."""

    tag = "fieldset"

    # Disables all the form control descendants of the fieldset
    disabled: Var_[Union[str, int, bool]]

    # Associates the fieldset with a form (by id)
    form: Var_[Union[str, int, bool]]

    # Name of the fieldset, used for scripting
    name: Var_[Union[str, int, bool]]


class Form(BaseHTML):
    """Display the form element."""

    tag = "form"

    # MIME types the server accepts for file upload
    accept: Var_[Union[str, int, bool]]

    # Character encodings to be used for form submission
    accept_charset: Var_[Union[str, int, bool]]

    # URL where the form's data should be submitted
    action: Var_[Union[str, int, bool]]

    # Whether the form should have autocomplete enabled
    auto_complete: Var_[Union[str, int, bool]]

    # Encoding type for the form data when submitted
    enc_type: Var_[Union[str, int, bool]]

    # HTTP method to use for form submission
    method: Var_[Union[str, int, bool]]

    # Name of the form
    name: Var_[Union[str, int, bool]]

    # Indicates that the form should not be validated on submit
    no_validate: Var_[Union[str, int, bool]]

    # Where to display the response after submitting the form
    target: Var_[Union[str, int, bool]]


class Input(BaseHTML):
    """Display the input element."""

    tag = "input"

    # Accepted types of files when the input is file type
    accept: Var_[Union[str, int, bool]]

    # Alternate text for input type="image"
    alt: Var_[Union[str, int, bool]]

    # Whether the input should have autocomplete enabled
    auto_complete: Var_[Union[str, int, bool]]

    # Automatically focuses the input when the page loads
    auto_focus: Var_[Union[str, int, bool]]

    # Captures media from the user (camera or microphone)
    capture: Var_[Union[str, int, bool]]

    # Indicates whether the input is checked (for checkboxes and radio buttons)
    checked: Var_[Union[str, int, bool]]

    # Name part of the input to submit in 'dir' and 'name' pair when form is submitted
    dirname: Var_[Union[str, int, bool]]

    # Disables the input
    disabled: Var_[Union[str, int, bool]]

    # Associates the input with a form (by id)
    form: Var_[Union[str, int, bool]]

    # URL to send the form data to (for type="submit" buttons)
    form_action: Var_[Union[str, int, bool]]

    # How the form data should be encoded when submitting to the server (for type="submit" buttons)
    form_enc_type: Var_[Union[str, int, bool]]

    # HTTP method to use for sending form data (for type="submit" buttons)
    form_method: Var_[Union[str, int, bool]]

    # Bypasses form validation when submitting (for type="submit" buttons)
    form_no_validate: Var_[Union[str, int, bool]]

    # Specifies where to display the response after submitting the form (for type="submit" buttons)
    form_target: Var_[Union[str, int, bool]]

    # The height of the input (only for type="image")
    height: Var_[Union[str, int, bool]]

    # References a datalist for suggested options
    list: Var_[Union[str, int, bool]]

    # Specifies the maximum value for the input
    max: Var_[Union[str, int, bool]]

    # Specifies the maximum number of characters allowed in the input
    max_length: Var_[Union[str, int, bool]]

    # Specifies the minimum number of characters required in the input
    min_length: Var_[Union[str, int, bool]]

    # Specifies the minimum value for the input
    min: Var_[Union[str, int, bool]]

    # Indicates whether multiple values can be entered in an input of the type email or file
    multiple: Var_[Union[str, int, bool]]

    # Name of the input, used when sending form data
    name: Var_[Union[str, int, bool]]

    # Regex pattern the input's value must match to be valid
    pattern: Var_[Union[str, int, bool]]

    # Placeholder text in the input
    placeholder: Var_[Union[str, int, bool]]

    # Indicates whether the input is read-only
    read_only: Var_[Union[str, int, bool]]

    # Indicates that the input is required
    required: Var_[Union[str, int, bool]]

    # Specifies the visible width of a text control
    size: Var_[Union[str, int, bool]]

    # URL for image inputs
    src: Var_[Union[str, int, bool]]

    # Specifies the legal number intervals for an input
    step: Var_[Union[str, int, bool]]

    # Specifies the type of input
    type: Var_[Union[str, int, bool]]

    # Name of the image map used with the input
    use_map: Var_[Union[str, int, bool]]

    # Value of the input
    value: Var_[Union[str, int, bool]]

    # The width of the input (only for type="image")
    width: Var_[Union[str, int, bool]]


class Label(BaseHTML):
    """Display the label element."""

    tag = "label"

    # ID of a form control with which the label is associated
    html_for: Var_[Union[str, int, bool]]

    # Associates the label with a form (by id)
    form: Var_[Union[str, int, bool]]


class Legend(BaseHTML):
    """Display the legend element."""

    tag = "legend"
    # No unique attributes, only common ones are inherited


class Meter(BaseHTML):
    """Display the meter element."""

    tag = "meter"

    # Associates the meter with a form (by id)
    form: Var_[Union[str, int, bool]]

    # High limit of range (above this is considered high value)
    high: Var_[Union[str, int, bool]]

    # Low limit of range (below this is considered low value)
    low: Var_[Union[str, int, bool]]

    # Maximum value of the range
    max: Var_[Union[str, int, bool]]

    # Minimum value of the range
    min: Var_[Union[str, int, bool]]

    # Optimum value in the range
    optimum: Var_[Union[str, int, bool]]

    # Current value of the meter
    value: Var_[Union[str, int, bool]]


class Optgroup(BaseHTML):
    """Display the optgroup element."""

    tag = "optgroup"

    # Disables the optgroup
    disabled: Var_[Union[str, int, bool]]

    # Label for the optgroup
    label: Var_[Union[str, int, bool]]


class Option(BaseHTML):
    """Display the option element."""

    tag = "option"

    # Disables the option
    disabled: Var_[Union[str, int, bool]]

    # Label for the option, if the text is not the label
    label: Var_[Union[str, int, bool]]

    # Indicates that the option is initially selected
    selected: Var_[Union[str, int, bool]]

    # Value to be sent as form data
    value: Var_[Union[str, int, bool]]


class Output(BaseHTML):
    """Display the output element."""

    tag = "output"

    # Associates the output with one or more elements (by their IDs)
    html_for: Var_[Union[str, int, bool]]

    # Associates the output with a form (by id)
    form: Var_[Union[str, int, bool]]

    # Name of the output element for form submission
    name: Var_[Union[str, int, bool]]


class Progress(BaseHTML):
    """Display the progress element."""

    tag = "progress"

    # Associates the progress element with a form (by id)
    form: Var_[Union[str, int, bool]]

    # Maximum value of the progress indicator
    max: Var_[Union[str, int, bool]]

    # Current value of the progress indicator
    value: Var_[Union[str, int, bool]]


class Select(BaseHTML):
    """Display the select element."""

    tag = "select"

    # Whether the form control should have autocomplete enabled
    auto_complete: Var_[Union[str, int, bool]]

    # Automatically focuses the select when the page loads
    auto_focus: Var_[Union[str, int, bool]]

    # Disables the select control
    disabled: Var_[Union[str, int, bool]]

    # Associates the select with a form (by id)
    form: Var_[Union[str, int, bool]]

    # Indicates that multiple options can be selected
    multiple: Var_[Union[str, int, bool]]

    # Name of the select, used when submitting the form
    name: Var_[Union[str, int, bool]]

    # Indicates that the select control must have a selected option
    required: Var_[Union[str, int, bool]]

    # Number of visible options in a drop-down list
    size: Var_[Union[str, int, bool]]


class Textarea(BaseHTML):
    """Display the textarea element."""

    tag = "textarea"

    # Whether the form control should have autocomplete enabled
    auto_complete: Var_[Union[str, int, bool]]

    # Automatically focuses the textarea when the page loads
    auto_focus: Var_[Union[str, int, bool]]

    # Visible width of the text control, in average character widths
    cols: Var_[Union[str, int, bool]]

    # Name part of the textarea to submit in 'dir' and 'name' pair when form is submitted
    dirname: Var_[Union[str, int, bool]]

    # Disables the textarea
    disabled: Var_[Union[str, int, bool]]

    # Associates the textarea with a form (by id)
    form: Var_[Union[str, int, bool]]

    # Maximum number of characters allowed in the textarea
    max_length: Var_[Union[str, int, bool]]

    # Minimum number of characters required in the textarea
    min_length: Var_[Union[str, int, bool]]

    # Name of the textarea, used when submitting the form
    name: Var_[Union[str, int, bool]]

    # Placeholder text in the textarea
    placeholder: Var_[Union[str, int, bool]]

    # Indicates whether the textarea is read-only
    read_only: Var_[Union[str, int, bool]]

    # Indicates that the textarea is required
    required: Var_[Union[str, int, bool]]

    # Visible number of lines in the text control
    rows: Var_[Union[str, int, bool]]

    # How the text in the textarea is to be wrapped when submitting the form
    wrap: Var_[Union[str, int, bool]]
