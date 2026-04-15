"""Forms classes."""

from __future__ import annotations

from collections.abc import Iterator
from hashlib import md5
from typing import Any, ClassVar, Literal

from reflex_base.components.component import field
from reflex_base.components.tags.tag import Tag
from reflex_base.constants import Dirs, EventTriggers
from reflex_base.event import (
    FORM_DATA,
    EventChain,
    EventHandler,
    checked_input_event,
    float_input_event,
    input_event,
    int_input_event,
    key_event,
    on_submit_event,
    on_submit_string_event,
    prevent_default,
)
from reflex_base.utils.imports import ImportDict
from reflex_base.vars import VarData
from reflex_base.vars.base import LiteralVar, Var
from reflex_base.vars.number import ternary_operation

from reflex_components_core.el.element import Element

from .base import BaseHTML


def _handle_submit_js_template(
    handle_submit_unique_name: str,
    form_data: str,
    field_ref_mapping: str,
    on_submit_event_chain: str,
    reset_on_submit: str,
) -> str:
    """Generate handle submit JS using f-string formatting.

    Args:
        handle_submit_unique_name: Unique name for the handle submit function.
        form_data: Name of the form data variable.
        field_ref_mapping: JSON string of field reference mappings.
        on_submit_event_chain: Event chain for the submit handler.
        reset_on_submit: Boolean string indicating if form should reset after submit.

    Returns:
        JavaScript code for the form submit handler.
    """
    return f"""
    const handleSubmit_{handle_submit_unique_name} = useCallback((ev) => {{
        const $form = ev.target
        ev.preventDefault()
        const {form_data} = {{...Object.fromEntries(new FormData($form).entries()), ...{field_ref_mapping}}};

        ({on_submit_event_chain}(ev));

        if ({reset_on_submit}) {{
            $form.reset()
        }}
    }})
    """


ButtonType = Literal["submit", "reset", "button"]


class Button(BaseHTML):
    """Display the button element."""

    tag = "button"

    auto_focus: Var[bool] = field(
        doc="Automatically focuses the button when the page loads"
    )

    disabled: Var[bool] = field(doc="Disables the button")

    form: Var[str] = field(doc="Associates the button with a form (by id)")

    form_action: Var[str] = field(
        doc='URL to send the form data to (for type="submit" buttons)'
    )

    form_enc_type: Var[str] = field(
        doc='How the form data should be encoded when submitting to the server (for type="submit" buttons)'
    )

    form_method: Var[str] = field(
        doc='HTTP method to use for sending form data (for type="submit" buttons)'
    )

    form_no_validate: Var[bool] = field(
        doc='Bypasses form validation when submitting (for type="submit" buttons)'
    )

    form_target: Var[str] = field(
        doc='Specifies where to display the response after submitting the form (for type="submit" buttons)'
    )

    name: Var[str] = field(doc="Name of the button, used when sending form data")

    type: Var[ButtonType] = field(doc="Type of the button (submit, reset, or button)")

    value: Var[str | int | float] = field(
        doc="Value of the button, used when sending form data"
    )

    _invalid_children: ClassVar[list[str]] = ["Button"]


class Datalist(BaseHTML):
    """Display the datalist element."""

    tag = "datalist"


class Fieldset(Element):
    """Display the fieldset element."""

    tag = "fieldset"

    disabled: Var[bool] = field(
        doc="Disables all the form control descendants of the fieldset"
    )

    form: Var[str] = field(doc="Associates the fieldset with a form (by id)")

    name: Var[str] = field(doc="Name of the fieldset, used for scripting")


class Form(BaseHTML):
    """Display the form element."""

    tag = "form"

    accept: Var[str] = field(doc="MIME types the server accepts for file upload")

    accept_charset: Var[str] = field(
        doc="Character encodings to be used for form submission"
    )

    action: Var[str] = field(doc="URL where the form's data should be submitted")

    auto_complete: Var[str] = field(
        doc="Whether the form should have autocomplete enabled"
    )

    enc_type: Var[str] = field(doc="Encoding type for the form data when submitted")

    method: Var[str] = field(doc="HTTP method to use for form submission")

    name: Var[str] = field(doc="Name of the form")

    no_validate: Var[bool] = field(
        doc="Indicates that the form should not be validated on submit"
    )

    target: Var[str] = field(
        doc="Where to display the response after submitting the form"
    )

    reset_on_submit: Var[bool] = field(
        default=Var.create(False), doc="If true, the form will be cleared after submit."
    )

    handle_submit_unique_name: Var[str] = field(
        doc="The name used to make this form's submit handler function unique."
    )

    on_submit: EventHandler[on_submit_event, on_submit_string_event] = field(
        doc="Fired when the form is submitted"
    )

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
        form.handle_submit_unique_name = md5(  # pyright: ignore[reportAttributeAccessIssue]
            str(form._get_all_hooks()).encode("utf-8")
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
            _handle_submit_js_template(
                handle_submit_unique_name=str(self.handle_submit_unique_name),
                form_data=str(FORM_DATA),
                field_ref_mapping=str(LiteralVar.create(self._get_form_refs())),
                on_submit_event_chain=str(
                    LiteralVar.create(self.event_triggers[EventTriggers.ON_SUBMIT])
                ),
                reset_on_submit=str(self.reset_on_submit).lower(),
            )
        ]

    def _render(self) -> Tag:
        render_tag = super()._render()
        if EventTriggers.ON_SUBMIT in self.event_triggers:
            render_tag = render_tag.add_props(**{
                EventTriggers.ON_SUBMIT: Var(
                    _js_expr=f"handleSubmit_{self.handle_submit_unique_name}",
                    _var_type=EventChain,
                )
            })
        return render_tag

    def _get_form_refs(self) -> dict[str, Any]:
        # Send all the input refs to the handler.
        form_refs = {}
        for ref in self._get_all_refs():
            # when ref start with refs_ it's an array of refs, so we need different method
            # to collect data
            if ref.startswith("refs_"):
                ref_var = Var(_js_expr=ref[:-3])._as_ref()
                form_refs[ref[len("refs_") : -3]] = Var(
                    _js_expr=f"getRefValues({ref_var!s})",
                    _var_data=VarData.merge(ref_var._get_all_var_data()),
                )
            else:
                ref_var = Var(_js_expr=ref)._as_ref()
                form_refs[ref[4:]] = Var(
                    _js_expr=f"getRefValue({ref_var!s})",
                    _var_data=VarData.merge(ref_var._get_all_var_data()),
                )
        return form_refs

    def _get_vars(
        self, include_children: bool = True, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        yield from super()._get_vars(
            include_children=include_children, ignore_ids=ignore_ids
        )
        yield from self._get_form_refs().values()

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "reset_on_submit",
            "handle_submit_unique_name",
        ]


HTMLInputTypeAttribute = Literal[
    "button",
    "checkbox",
    "color",
    "date",
    "datetime-local",
    "email",
    "file",
    "hidden",
    "image",
    "month",
    "number",
    "password",
    "radio",
    "range",
    "reset",
    "search",
    "submit",
    "tel",
    "text",
    "time",
    "url",
    "week",
]


class BaseInput(BaseHTML):
    """A base class for input elements."""

    tag = "input"

    accept: Var[str] = field(doc="Accepted types of files when the input is file type")

    alt: Var[str] = field(doc='Alternate text for input type="image"')

    auto_complete: Var[str] = field(
        doc="Whether the input should have autocomplete enabled"
    )

    auto_focus: Var[bool] = field(
        doc="Automatically focuses the input when the page loads"
    )

    capture: Var[Literal["user", "environment"] | bool] = field(
        doc="Captures media from the user (camera or microphone)"
    )

    checked: Var[bool] = field(
        doc="Indicates whether the input is checked (for checkboxes and radio buttons)"
    )

    default_checked: Var[bool] = field(
        doc="The initial value (for checkboxes and radio buttons)"
    )

    default_value: Var[str | int | float] = field(
        doc="The initial value for a text field"
    )

    disabled: Var[bool] = field(doc="Disables the input")

    form: Var[str] = field(doc="Associates the input with a form (by id)")

    form_action: Var[str] = field(
        doc='URL to send the form data to (for type="submit" buttons)'
    )

    form_enc_type: Var[str] = field(
        doc='How the form data should be encoded when submitting to the server (for type="submit" buttons)'
    )

    form_method: Var[str] = field(
        doc='HTTP method to use for sending form data (for type="submit" buttons)'
    )

    form_no_validate: Var[bool] = field(
        doc='Bypasses form validation when submitting (for type="submit" buttons)'
    )

    form_target: Var[str] = field(
        doc='Specifies where to display the response after submitting the form (for type="submit" buttons)'
    )

    list: Var[str] = field(doc="References a datalist for suggested options")

    max: Var[str | int | float] = field(doc="Specifies the maximum value for the input")

    max_length: Var[int | float] = field(
        doc="Specifies the maximum number of characters allowed in the input"
    )

    min_length: Var[int | float] = field(
        doc="Specifies the minimum number of characters required in the input"
    )

    min: Var[str | int | float] = field(doc="Specifies the minimum value for the input")

    multiple: Var[bool] = field(
        doc="Indicates whether multiple values can be entered in an input of the type email or file"
    )

    name: Var[str] = field(doc="Name of the input, used when sending form data")

    pattern: Var[str] = field(
        doc="Regex pattern the input's value must match to be valid"
    )

    placeholder: Var[str] = field(doc="Placeholder text in the input")

    read_only: Var[bool] = field(doc="Indicates whether the input is read-only")

    required: Var[bool] = field(doc="Indicates that the input is required")

    size: Var[str | int | float] = field(
        doc="Specifies the visible width of a text control"
    )

    src: Var[str] = field(doc="URL for image inputs")

    step: Var[str | int | float] = field(
        doc="Specifies the legal number intervals for an input"
    )

    type: Var[HTMLInputTypeAttribute] = field(doc="Specifies the type of input")

    value: Var[str | int | float] = field(doc="Value of the input")

    on_key_down: EventHandler[key_event] = field(doc="Fired when a key is pressed down")

    on_key_up: EventHandler[key_event] = field(doc="Fired when a key is released")


class CheckboxInput(BaseInput):
    """Display the input element."""

    on_change: EventHandler[checked_input_event] = field(
        doc="Fired when the input value changes"
    )

    on_focus: EventHandler[checked_input_event] = field(
        doc="Fired when the input gains focus"
    )

    on_blur: EventHandler[checked_input_event] = field(
        doc="Fired when the input loses focus"
    )


class ValueNumberInput(BaseInput):
    """Display the input element."""

    on_change: EventHandler[float_input_event, int_input_event, input_event] = field(
        doc="Fired when the input value changes"
    )

    on_focus: EventHandler[float_input_event, int_input_event, input_event] = field(
        doc="Fired when the input gains focus"
    )

    on_blur: EventHandler[float_input_event, int_input_event, input_event] = field(
        doc="Fired when the input loses focus"
    )


class Input(BaseInput):
    """Display the input element."""

    on_change: EventHandler[input_event] = field(
        doc="Fired when the input value changes"
    )

    on_focus: EventHandler[input_event] = field(doc="Fired when the input gains focus")

    on_blur: EventHandler[input_event] = field(doc="Fired when the input loses focus")

    @classmethod
    def create(cls, *children, **props):
        """Create an Input component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        value = props.get("value")

        # React expects an empty string(instead of null) for controlled inputs.
        if value is not None:
            value_var = Var.create(value)
            props["value"] = ternary_operation(
                value_var.is_not_none(), value_var, Var.create("")
            )

        if cls is Input:
            input_type = props.get("type")

            if isinstance(input_type, str) and input_type == "checkbox":
                # Checkbox inputs should use the CheckboxInput class
                return CheckboxInput.create(*children, **props)

            if isinstance(input_type, str) and (
                input_type == "number" or input_type == "range"
            ):
                # Number inputs should use the ValueNumberInput class
                return ValueNumberInput.create(*children, **props)

        return super().create(*children, **props)


class Label(BaseHTML):
    """Display the label element."""

    tag = "label"

    html_for: Var[str] = field(
        doc="ID of a form control with which the label is associated"
    )

    form: Var[str] = field(doc="Associates the label with a form (by id)")


class Legend(BaseHTML):
    """Display the legend element."""

    tag = "legend"


class Meter(BaseHTML):
    """Display the meter element."""

    tag = "meter"

    form: Var[str] = field(doc="Associates the meter with a form (by id)")

    high: Var[str | int | float] = field(
        doc="High limit of range (above this is considered high value)"
    )

    low: Var[str | int | float] = field(
        doc="Low limit of range (below this is considered low value)"
    )

    max: Var[str | int | float] = field(doc="Maximum value of the range")

    min: Var[str | int | float] = field(doc="Minimum value of the range")

    optimum: Var[str | int | float] = field(doc="Optimum value in the range")

    value: Var[str | int | float] = field(doc="Current value of the meter")


class Optgroup(BaseHTML):
    """Display the optgroup element."""

    tag = "optgroup"

    disabled: Var[bool] = field(doc="Disables the optgroup")

    label: Var[str] = field(doc="Label for the optgroup")


class Option(BaseHTML):
    """Display the option element."""

    tag = "option"

    disabled: Var[bool] = field(doc="Disables the option")

    label: Var[str] = field(doc="Label for the option, if the text is not the label")

    selected: Var[bool] = field(doc="Indicates that the option is initially selected")

    value: Var[str | int | float] = field(doc="Value to be sent as form data")


class Output(BaseHTML):
    """Display the output element."""

    tag = "output"

    html_for: Var[str] = field(
        doc="Associates the output with one or more elements (by their IDs)"
    )

    form: Var[str] = field(doc="Associates the output with a form (by id)")

    name: Var[str] = field(doc="Name of the output element for form submission")


class Progress(BaseHTML):
    """Display the progress element."""

    tag = "progress"

    form: Var[str] = field(doc="Associates the progress element with a form (by id)")

    max: Var[str | int | float] = field(doc="Maximum value of the progress indicator")

    value: Var[str | int | float] = field(doc="Current value of the progress indicator")


class Select(BaseHTML):
    """Display the select element."""

    tag = "select"

    auto_complete: Var[str] = field(
        doc="Whether the form control should have autocomplete enabled"
    )

    auto_focus: Var[bool] = field(
        doc="Automatically focuses the select when the page loads"
    )

    disabled: Var[bool] = field(doc="Disables the select control")

    form: Var[str] = field(doc="Associates the select with a form (by id)")

    multiple: Var[bool] = field(doc="Indicates that multiple options can be selected")

    name: Var[str] = field(doc="Name of the select, used when submitting the form")

    required: Var[bool] = field(
        doc="Indicates that the select control must have a selected option"
    )

    size: Var[str | int] = field(doc="Number of visible options in a drop-down list")

    on_change: EventHandler[input_event] = field(
        doc="Fired when the select value changes"
    )

    value: Var[str] = field(
        doc="The controlled value of the select, read only unless used with on_change"
    )

    default_value: Var[str] = field(
        doc="The default value of the select when initially rendered"
    )


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

    auto_complete: Var[str] = field(
        doc="Whether the form control should have autocomplete enabled"
    )

    auto_focus: Var[bool] = field(
        doc="Automatically focuses the textarea when the page loads"
    )

    auto_height: Var[bool] = field(
        doc="Automatically fit the content height to the text (use min-height with this prop)"
    )

    cols: Var[str | int] = field(
        doc="Visible width of the text control, in average character widths"
    )

    default_value: Var[str] = field(
        doc="The default value of the textarea when initially rendered"
    )

    dirname: Var[str] = field(
        doc="Name part of the textarea to submit in 'dir' and 'name' pair when form is submitted"
    )

    disabled: Var[bool] = field(doc="Disables the textarea")

    enter_key_submit: Var[bool] = field(
        doc="Enter key submits form (shift-enter adds new line)"
    )

    form: Var[str] = field(doc="Associates the textarea with a form (by id)")

    max_length: Var[str | int] = field(
        doc="Maximum number of characters allowed in the textarea"
    )

    min_length: Var[str | int] = field(
        doc="Minimum number of characters required in the textarea"
    )

    name: Var[str] = field(doc="Name of the textarea, used when submitting the form")

    placeholder: Var[str] = field(doc="Placeholder text in the textarea")

    read_only: Var[bool] = field(doc="Indicates whether the textarea is read-only")

    required: Var[bool] = field(doc="Indicates that the textarea is required")

    rows: Var[str | int] = field(doc="Visible number of lines in the text control")

    value: Var[str] = field(
        doc="The controlled value of the textarea, read only unless used with on_change"
    )

    wrap: Var[str] = field(
        doc="How the text in the textarea is to be wrapped when submitting the form"
    )

    on_change: EventHandler[input_event] = field(
        doc="Fired when the input value changes"
    )

    on_focus: EventHandler[input_event] = field(doc="Fired when the input gains focus")

    on_blur: EventHandler[input_event] = field(doc="Fired when the input loses focus")

    on_key_down: EventHandler[key_event] = field(doc="Fired when a key is pressed down")

    on_key_up: EventHandler[key_event] = field(doc="Fired when a key is released")

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
                msg = "Cannot combine `enter_key_submit` with `on_key_down`."
                raise ValueError(msg)
            custom_attrs["on_key_down"] = Var(
                _js_expr=f"(e) => enterKeySubmitOnKeyDown(e, {enter_key_submit!s})",
                _var_data=VarData.merge(enter_key_submit._get_all_var_data()),
            )
        if auto_height is not None:
            auto_height = Var.create(auto_height)
            custom_attrs["on_input"] = Var(
                _js_expr=f"(e) => autoHeightOnInput(e, {auto_height!s})",
                _var_data=VarData.merge(auto_height._get_all_var_data()),
            )
        return super().create(*children, **props)

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "auto_height",
            "enter_key_submit",
        ]

    def _get_all_custom_code(self) -> dict[str, None]:
        """Include the custom code for auto_height and enter_key_submit functionality.

        Returns:
            The custom code for the component.
        """
        custom_code = super()._get_all_custom_code()
        if self.auto_height is not None:
            custom_code[AUTO_HEIGHT_JS] = None
        if self.enter_key_submit is not None:
            custom_code[ENTER_KEY_SUBMIT_JS] = None
        return custom_code


button = Button.create
datalist = Datalist.create
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
