"""Radix form component."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from reflex_base.components.component import ComponentNamespace, field
from reflex_base.event import EventHandler, no_args_event_spec
from reflex_base.utils.form import FormData as _FormData
from reflex_base.vars.base import Var
from reflex_components_core.core.debounce import DebounceInput
from reflex_components_core.el.elements.forms import BaseInput, Select, Textarea
from reflex_components_core.el.elements.forms import Form as HTMLForm

from .base import RadixPrimitiveComponentWithClassName

# Radix Form.Control composes with native form controls only: an input, select
# or textarea, or a component rendering one. Its other primitives, such as
# Checkbox and Select, do not compose with it.
_FORM_CONTROL_CHILD_TYPES = (BaseInput, Select, Textarea, DebounceInput)


class FormComponent(RadixPrimitiveComponentWithClassName):
    """Base class for all @radix-ui/react-form components."""

    library = "@radix-ui/react-form@0.3.0"


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

    # Radix passes the field's name to the control its ``FormControl`` renders.
    _is_form_field = True

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

    # Renders an input, or its child with ``as_child``, named by the enclosing
    # ``FormField`` unless the control or its child carries a ``name``.
    _is_form_field_control = True

    name: Var[str] = field(
        doc="The name of the control, in place of the name of the enclosing form field."
    )

    @classmethod
    def create(cls, *children, **props):
        """Create a Form Control component.

        The control renders an input, or the native form control its child
        renders, which then takes the enclosing form field's name and
        validation messages.

        Args:
            *children: The control to render, if any.
            **props: The properties of the form control.

        Returns:
            The form control component.

        Raises:
            ValueError: If more than one child is given.
            TypeError: If the child does not render a native form control.
        """
        if len(children) > 1:
            msg = f"FormControl can only have at most one child, got {len(children)} children"
            raise ValueError(msg)
        for child in children:
            if not isinstance(child, _FORM_CONTROL_CHILD_TYPES):
                msg = (
                    "The child of rx.form.control must render a native form "
                    "control: rx.input, rx.text_area, rx.debounce_input, "
                    "rx.el.input, rx.el.select or rx.el.textarea, not "
                    f"{type(child).__name__}. Radix forms do not compose with "
                    "other controls such as rx.checkbox or rx.select; give those "
                    "a `name` and place them under rx.form.root or rx.form.field "
                    "instead."
                )
                raise TypeError(msg)
            # Radix renders the child as the control only with asChild.
            props.setdefault("as_child", True)
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

    def _exclude_props(self) -> list[str]:
        """Exclude force_match when match is not set.

        Radix only reads forceMatch together with match. Without match it passes
        forceMatch through to the DOM element, and React logs an unknown prop.

        Returns:
            The props to exclude.
        """
        if self.match is None:
            return [*super()._exclude_props(), "force_match"]
        return super()._exclude_props()


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

    # Stubbed as a class so ``rx.form.FormData`` works in type annotations.
    _stub_as_class: ClassVar[bool] = True

    root = staticmethod(FormRoot.create)
    control = staticmethod(FormControl.create)
    field = staticmethod(FormField.create)
    label = staticmethod(FormLabel.create)
    message = staticmethod(FormMessage.create)
    submit = staticmethod(FormSubmit.create)
    validity_state = staticmethod(FormValidityState.create)
    FormData = _FormData
    __call__ = staticmethod(Form.create)


form = FormNamespace()
