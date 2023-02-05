"""Form components."""

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class FormControl(ChakraComponent):
    """Provide context to form components."""

    tag = "FormControl"

    # If true, the form control will be disabled.
    is_disabled: Var[bool]

    # If true, the form control will be invalid.
    is_invalid: Var[bool]

    # If true, the form control will be readonly
    is_read_only: Var[bool]

    # If true, the form control will be required.
    is_required: Var[bool]

    # The label text used to inform users as to what information is requested for a text field.
    label: Var[str]

    @classmethod
    def create(
        cls,
        *children,
        label=None,
        input=None,
        help_text=None,
        error_message=None,
        **props
    ) -> Component:
        """Create a form control component.

        Args:
            children: The children of the form control.
            label: The label of the form control.
            input: The input of the form control.
            help_text: The help text of the form control.
            error_message: The error message of the form control.
            props: The properties of the form control.

        Raises:
            AttributeError: raise an error if missing required kwargs.

        Returns:
            The form control component.
        """
        if len(children) == 0:
            children = []

            if label:
                children.append(FormLabel.create(*label))

            if not input:
                raise AttributeError("input keyword argument is required")
            children.append(input)

            if help_text:
                children.append(FormHelperText.create(*help_text))

            if error_message:
                children.append(FormErrorMessage.create(*error_message))

        return super().create(*children, **props)


class FormHelperText(ChakraComponent):
    """A form helper text component."""

    tag = "FormHelperText"


class FormLabel(ChakraComponent):
    """A form label component."""

    tag = "FormLabel"

    # Link
    html_for: Var[str]


class FormErrorMessage(ChakraComponent):
    """A form error message component."""

    tag = "FormErrorMessage"
