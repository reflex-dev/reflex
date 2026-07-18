"""Radix form component."""

from __future__ import annotations

from typing import Any, Literal

from reflex_base.components.component import ComponentNamespace, field
from reflex_base.event import EventHandler, no_args_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.core.debounce import DebounceInput
from reflex_components_core.el.elements.forms import Form as HTMLForm

from reflex_components_radix.themes.components.text_field import TextFieldRoot

from .base import RadixPrimitiveComponentWithClassName


class FormComponent(RadixPrimitiveComponentWithClassName):
    """Base class for all @radix-ui/react-form components."""

    library = "@radix-ui/react-form@0.1.8"


class FormRoot(FormComponent, HTMLForm):
    """The root component of a radix form."""

    tag = "Root"

    alias = "RadixFormRoot"

    on_clear_server_errors: EventHandler[no_args_event_spec] = field(
        doc="Fired when the errors are cleared."
    )

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        return {"width": "100%"}


class FormField(FormComponent):
    """A form field component."""

    tag = "Field"

    alias = "RadixFormField"

    name: Var[str] = field(
        doc="The name of the form field, that is passed down to the control and used to match with validation messages."
    )

    server_invalid: Var[bool] = field(
        doc="Flag to mark the form field as invalid, for server side validation."
    )

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        return {"display": "grid", "margin_bottom": "10px"}


class FormLabel(FormComponent):
    """A form label component."""

    tag = "Label"

    alias = "RadixFormLabel"

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        return {"font_size": "15px", "font_weight": "500", "line_height": "35px"}


class FormControl(FormComponent):
    """A form control component."""

    tag = "Control"

    alias = "RadixFormControl"

    @classmethod
    def create(cls, *children, **props):
        """Create a Form Control component.

        Args:
            *children: The children of the form.
            **props: The properties of the form.

        Returns:
            The form control component.

        Raises:
            ValueError: If the number of children is greater than 1.
            TypeError: If a child exists but it is not a TextFieldInput.
        """
        if len(children) > 1:
            msg = f"FormControl can only have at most one child, got {len(children)} children"
            raise ValueError(msg)
        for child in children:
            if not isinstance(child, (TextFieldRoot, DebounceInput)):
                msg = "Only Radix TextFieldRoot and DebounceInput are allowed as children of FormControl"
                raise TypeError(msg)
        return super().create(*children, **props)


LiteralMatcher = Literal[
    "badInput",
    "patternMismatch",
    "rangeOverflow",
    "rangeUnderflow",
    "stepMismatch",
    "tooLong",
    "tooShort",
    "typeMismatch",
    "valid",
    "valueMissing",
]


class FormMessage(FormComponent):
    """A form message component."""

    tag = "Message"

    alias = "RadixFormMessage"

    name: Var[str] = field(
        doc="Used to target a specific field by name when rendering outside of a Field part."
    )

    match: Var[LiteralMatcher] = field(
        doc="Used to indicate on which condition the message should be visible."
    )

    force_match: Var[bool] = field(
        doc="Forces the message to be shown. This is useful when using server-side validation."
    )

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        return {"font_size": "13px", "opacity": "0.8", "color": "white"}


class FormValidityState(FormComponent):
    """A form validity state component."""

    tag = "ValidityState"
    alias = "RadixFormValidityState"


class FormSubmit(FormComponent):
    """A form submit component."""

    tag = "Submit"
    alias = "RadixFormSubmit"


# This class is created mainly for reflex-web docs.
class Form(FormRoot):
    """The Form component."""


class FormNamespace(ComponentNamespace):
    """Form components."""

    root = staticmethod(FormRoot.create)
    control = staticmethod(FormControl.create)
    field = staticmethod(FormField.create)
    label = staticmethod(FormLabel.create)
    message = staticmethod(FormMessage.create)
    submit = staticmethod(FormSubmit.create)
    validity_state = staticmethod(FormValidityState.create)
    __call__ = staticmethod(Form.create)


form = FormNamespace()
