"""Custom OTP field component."""

from typing import Literal

from reflex.components.component import Component, ComponentNamespace
from reflex.event import EventHandler, passthrough_event_spec
from reflex.utils.imports import ImportVar
from reflex.vars.base import Var
from reflex_components_internal.components.base_ui import PACKAGE_NAME, BaseUIComponent

LiteralValidationType = Literal["numeric", "alpha", "alphanumeric", "none"]
LiteralInputMode = Literal[
    "none", "text", "tel", "url", "email", "numeric", "decimal", "search"
]
LiteralOrientation = Literal["horizontal", "vertical"]

on_value_event_spec = passthrough_event_spec(str, dict)


class ClassNames:
    """Class names for OTP field components."""

    ROOT = "flex flex-row items-center gap-2"
    INPUT = "size-10 rounded-ui-md border border-secondary-4 bg-white dark:bg-secondary-3 text-secondary-12 text-center text-base font-medium outline-none transition-[color,box-shadow] hover:border-secondary-a6 focus:border-primary-a6 focus:shadow-[0px_0px_0px_2px_var(--primary-4)] data-[disabled]:cursor-not-allowed data-[disabled]:border-secondary-4 data-[disabled]:bg-secondary-3 data-[disabled]:text-secondary-8 data-[invalid]:border-destructive-10 data-[invalid]:focus:border-destructive-a11 data-[invalid]:focus:shadow-[0px_0px_0px_2px_var(--destructive-4)] data-[invalid]:hover:border-destructive-a11 shadow-[0_1px_2px_0_rgba(0,0,0,0.02),0_1px_4px_0_rgba(0,0,0,0.02)] dark:shadow-none dark:border-secondary-5"
    SEPARATOR = "text-secondary-9 text-base font-medium select-none"


class OTPFieldBaseComponent(BaseUIComponent):
    """Base component for OTP field components."""

    library = f"{PACKAGE_NAME}/otp-field"

    @property
    def import_var(self):
        """Return the import variable for the OTP field component."""
        return ImportVar(tag="OTPFieldPreview", package_path="", install=False)


class OTPFieldRoot(OTPFieldBaseComponent):
    """Container that manages state for one-time password entry across multiple slots. Renders a div."""

    tag = "OTPFieldPreview.Root"

    # The number of input slots. Required.
    length: Var[int]

    # Identifies the field when a form is submitted.
    name: Var[str]

    # The controlled OTP value. To render an uncontrolled field, use the default_value prop instead.
    value: Var[str]

    # The uncontrolled initial value. To render a controlled field, use the value prop instead.
    default_value: Var[str]

    # Browser autocomplete hint. Defaults to "one-time-code".
    auto_complete: Var[str]

    # The virtual keyboard type for the inputs.
    input_mode: Var[LiteralInputMode]

    # Input validation rule. Defaults to "numeric".
    validation_type: Var[LiteralValidationType]

    # Whether characters are obscured while typing. Defaults to False.
    mask: Var[bool]

    # Whether the form is auto-submitted when all slots fill. Defaults to False.
    auto_submit: Var[bool]

    # The id of a <form> element to associate with.
    form: Var[str]

    # Whether the field should ignore user interaction. Defaults to False.
    disabled: Var[bool]

    # Whether the user should be unable to modify the value. Defaults to False.
    read_only: Var[bool]

    # Whether the field is required. Defaults to False.
    required: Var[bool]

    # Event handler called on input, paste, or keyboard changes.
    on_value_change: EventHandler[on_value_event_spec]

    # Event handler called when characters are rejected by sanitization.
    on_value_invalid: EventHandler[on_value_event_spec]

    # Event handler called when all slots fill.
    on_value_complete: EventHandler[on_value_event_spec]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the OTP field root component.

        Returns:
            The component.
        """
        props["data-slot"] = "otp-field"
        cls.set_class_name(ClassNames.ROOT, props)
        return super().create(*children, **props)


class OTPFieldInput(OTPFieldBaseComponent):
    """An individual character slot. Renders an input element."""

    tag = "OTPFieldPreview.Input"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the OTP field input component.

        Returns:
            The component.
        """
        props["data-slot"] = "otp-field-input"
        cls.set_class_name(ClassNames.INPUT, props)
        return super().create(*children, **props)


class OTPFieldSeparator(OTPFieldBaseComponent):
    """A visual or semantic divider between input groups. Renders a div."""

    tag = "OTPFieldPreview.Separator"

    # The separator orientation. Defaults to "horizontal".
    orientation: Var[LiteralOrientation]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the OTP field separator component.

        Returns:
            The component.
        """
        props["data-slot"] = "otp-field-separator"
        cls.set_class_name(ClassNames.SEPARATOR, props)
        return super().create(*children, **props)


class HighLevelOTPField(OTPFieldRoot):
    """High-level wrapper for the OTP field component."""

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create a complete OTP field component.

        Renders a Root with `length` Input slots when no children are
        provided. Pass children explicitly to customize layout (e.g. inserting
        a Separator between groups of inputs); `length` is still required and
        forwarded to the underlying Root.

        Args:
            *children: Optional children to include in place of the default inputs.
            **props: Additional properties to apply to the OTP field root.

        Returns:
            The OTP field component.

        Raises:
            ValueError: If `length` is missing when children are supplied, or
                if `length` is not a positive integer when children are
                auto-generated.
            TypeError: If `length` is not an integer when children are
                auto-generated (a Var can only be used with explicit children).
        """
        if children:
            if "length" not in props:
                msg = "OTP field `length` is required when passing children explicitly."
                raise ValueError(msg)
        else:
            length = props.setdefault("length", 6)
            if not isinstance(length, int) or isinstance(length, bool):
                msg = (
                    "OTP field high-level wrapper requires a static integer `length`."
                    " Pass children explicitly for dynamic lengths."
                )
                raise TypeError(msg)
            if length <= 0:
                msg = "OTP field `length` must be a positive integer."
                raise ValueError(msg)
            children = tuple(OTPFieldInput.create() for _ in range(length))

        return OTPFieldRoot.create(*children, **props)


class OTPField(ComponentNamespace):
    """Namespace for OTP field components."""

    root = staticmethod(OTPFieldRoot.create)
    input = staticmethod(OTPFieldInput.create)
    separator = staticmethod(OTPFieldSeparator.create)
    class_names = ClassNames
    __call__ = staticmethod(HighLevelOTPField.create)


otp_field = OTPField()
