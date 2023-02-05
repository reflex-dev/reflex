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
    def create(cls, *children, **props) -> Component:
        if not children:
            children = []
            prop_label = props.pop("label", None)
            prop_input = props.pop("input")
            prop_helptext = props.pop("help_text", None)
            prop_errormessage = props.pop("error_message", None)

            if prop_label:
                children.append(FormLabel.create(*prop_label))

            children.append(prop_input)

            if prop_helptext:
                children.append(FormHelperText.create(*prop_helptext))

            if prop_errormessage:
                children.append(FormErrorMessage.create(*prop_errormessage))

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
