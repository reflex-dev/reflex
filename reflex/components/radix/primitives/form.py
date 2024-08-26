"""Radix form component."""

from __future__ import annotations

from typing import Any, Literal

from reflex.components.component import ComponentNamespace
from reflex.components.core.debounce import DebounceInput
from reflex.components.el.elements.forms import Form as HTMLForm
from reflex.components.radix.themes.components.text_field import TextFieldRoot
from reflex.event import EventHandler
from reflex.vars import Var

from .base import RadixPrimitiveComponentWithClassName


class FormComponent(RadixPrimitiveComponentWithClassName):
    """Base class for all @radix-ui/react-form components."""

    library = "@radix-ui/react-form@^0.0.3"


class FormRoot(FormComponent, HTMLForm):
    """The root component of a radix form."""

    tag = "Root"

    alias = "RadixFormRoot"

    # Fired when the errors are cleared.
    on_clear_server_errors: EventHandler[lambda: []]

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

    # The name of the form field, that is passed down to the control and used to match with validation messages.
    name: Var[str]

    # Flag to mark the form field as invalid, for server side validation.
    server_invalid: Var[bool]

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

        Raises:
            ValueError: If the number of children is greater than 1.
            TypeError: If a child exists but it is not a TextFieldInput.

        Returns:
            The form control component.
        """
        if len(children) > 1:
            raise ValueError(
                f"FormControl can only have at most one child, got {len(children)} children"
            )
        for child in children:
            if not isinstance(child, (TextFieldRoot, DebounceInput)):
                raise TypeError(
                    "Only Radix TextFieldRoot and DebounceInput are allowed as children of FormControl"
                )
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

    # Used to target a specific field by name when rendering outside of a Field part.
    name: Var[str]

    # Used to indicate on which condition the message should be visible.
    match: Var[LiteralMatcher]

    # Forces the message to be shown. This is useful when using server-side validation.
    force_match: Var[bool]

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

    pass


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
