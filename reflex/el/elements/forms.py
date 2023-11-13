"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Union

from reflex.el.element import Element
from reflex.vars import Var as Var_

from .base import BaseHTML


class Button(BaseHTML):
    """Display the button element."""

    tag = "button"

    auto_focus: Var_[Union[str, int, bool]]
    disabled: Var_[Union[str, int, bool]]
    form: Var_[Union[str, int, bool]]
    form_action: Var_[Union[str, int, bool]]
    form_enc_type: Var_[Union[str, int, bool]]
    form_method: Var_[Union[str, int, bool]]
    form_no_validate: Var_[Union[str, int, bool]]
    form_target: Var_[Union[str, int, bool]]
    name: Var_[Union[str, int, bool]]
    type: Var_[Union[str, int, bool]]
    value: Var_[Union[str, int, bool]]


class Datalist(BaseHTML):  # noqa: E742
    """Display the datalist element."""

    tag = "datalist"


class Fieldset(Element):  # noqa: E742
    """Display the fieldset element."""

    tag = "fieldset"
    disabled: Var_[Union[str, int, bool]]
    form: Var_[Union[str, int, bool]]
    name: Var_[Union[str, int, bool]]


class Form(BaseHTML):  # noqa: E742
    """Display the form element."""

    tag = "form"

    tag = "form"
    accept: Var_[Union[str, int, bool]]
    accept_charset: Var_[Union[str, int, bool]]
    action: Var_[Union[str, int, bool]]
    auto_complete: Var_[Union[str, int, bool]]
    enc_type: Var_[Union[str, int, bool]]
    method: Var_[Union[str, int, bool]]
    name: Var_[Union[str, int, bool]]
    no_validate: Var_[Union[str, int, bool]]
    target: Var_[Union[str, int, bool]]


class Input(BaseHTML):
    """Display the input element."""

    tag = "input"

    accept: Var_[Union[str, int, bool]]
    alt: Var_[Union[str, int, bool]]
    auto_complete: Var_[Union[str, int, bool]]
    auto_focus: Var_[Union[str, int, bool]]
    capture: Var_[Union[str, int, bool]]
    checked: Var_[Union[str, int, bool]]
    dirname: Var_[Union[str, int, bool]]
    disabled: Var_[Union[str, int, bool]]
    form: Var_[Union[str, int, bool]]
    form_action: Var_[Union[str, int, bool]]
    form_enc_type: Var_[Union[str, int, bool]]
    form_method: Var_[Union[str, int, bool]]
    form_no_validate: Var_[Union[str, int, bool]]
    form_target: Var_[Union[str, int, bool]]
    height: Var_[Union[str, int, bool]]
    list: Var_[Union[str, int, bool]]
    max: Var_[Union[str, int, bool]]
    max_length: Var_[Union[str, int, bool]]
    min_length: Var_[Union[str, int, bool]]
    min: Var_[Union[str, int, bool]]
    multiple: Var_[Union[str, int, bool]]
    name: Var_[Union[str, int, bool]]
    pattern: Var_[Union[str, int, bool]]
    placeholder: Var_[Union[str, int, bool]]
    read_only: Var_[Union[str, int, bool]]
    required: Var_[Union[str, int, bool]]
    size: Var_[Union[str, int, bool]]
    src: Var_[Union[str, int, bool]]
    step: Var_[Union[str, int, bool]]
    type: Var_[Union[str, int, bool]]
    use_map: Var_[Union[str, int, bool]]
    value: Var_[Union[str, int, bool]]
    width: Var_[Union[str, int, bool]]


class Label(BaseHTML):  # noqa: E742
    """Display the label element."""

    tag = "label"

    html_for: Var_[Union[str, int, bool]]
    form: Var_[Union[str, int, bool]]


class Legend(BaseHTML):  # noqa: E742
    """Display the legend element."""

    tag = "legend"


class Meter(BaseHTML):
    """Display the meter element."""

    tag = "meter"
    form: Var_[Union[str, int, bool]]
    high: Var_[Union[str, int, bool]]
    low: Var_[Union[str, int, bool]]
    max: Var_[Union[str, int, bool]]
    min: Var_[Union[str, int, bool]]
    optimum: Var_[Union[str, int, bool]]
    value: Var_[Union[str, int, bool]]


class Optgroup(BaseHTML):
    """Display the optgroup element."""

    tag = "optgroup"
    disabled: Var_[Union[str, int, bool]]
    label: Var_[Union[str, int, bool]]


class Option(BaseHTML):
    """Display the option element."""

    tag = "option"
    disabled: Var_[Union[str, int, bool]]
    label: Var_[Union[str, int, bool]]
    selected: Var_[Union[str, int, bool]]
    value: Var_[Union[str, int, bool]]


class Output(BaseHTML):
    """Display the output element."""

    tag = "output"
    html_for: Var_[Union[str, int, bool]]
    form: Var_[Union[str, int, bool]]
    name: Var_[Union[str, int, bool]]


class Progress(BaseHTML):
    """Display the progress element."""

    tag = "progress"
    form: Var_[Union[str, int, bool]]
    max: Var_[Union[str, int, bool]]
    value: Var_[Union[str, int, bool]]


class Select(BaseHTML):
    """Display the select element."""

    tag = "select"
    auto_complete: Var_[Union[str, int, bool]]
    auto_focus: Var_[Union[str, int, bool]]
    disabled: Var_[Union[str, int, bool]]
    form: Var_[Union[str, int, bool]]
    multiple: Var_[Union[str, int, bool]]
    name: Var_[Union[str, int, bool]]
    required: Var_[Union[str, int, bool]]
    size: Var_[Union[str, int, bool]]


class Textarea(BaseHTML):
    """Display the textarea element."""

    tag = "textarea"
    auto_complete: Var_[Union[str, int, bool]]
    auto_focus: Var_[Union[str, int, bool]]
    cols: Var_[Union[str, int, bool]]
    dirname: Var_[Union[str, int, bool]]
    disabled: Var_[Union[str, int, bool]]
    form: Var_[Union[str, int, bool]]
    max_length: Var_[Union[str, int, bool]]
    min_length: Var_[Union[str, int, bool]]
    name: Var_[Union[str, int, bool]]
    placeholder: Var_[Union[str, int, bool]]
    read_only: Var_[Union[str, int, bool]]
    required: Var_[Union[str, int, bool]]
    rows: Var_[Union[str, int, bool]]
    wrap: Var_[Union[str, int, bool]]
