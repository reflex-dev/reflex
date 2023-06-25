"""An editable component."""

from typing import Dict

from reflex.components.libs.chakra import ChakraComponent
from reflex.event import EVENT_ARG
from reflex.vars import Var


class Editable(ChakraComponent):
    """The wrapper component that provides context value."""

    tag = "Editable"

    # If true, the Editable will be disabled.
    is_disabled: Var[bool]

    # If true, the read only view, has a tabIndex set to 0 so it can receive focus via the keyboard or click.
    is_preview_focusable: Var[bool]

    # The placeholder text when the value is empty.
    placeholder: Var[str]

    # If true, the input's text will be highlighted on focus.
    select_all_on_focus: Var[bool]

    # If true, the Editable will start with edit mode by default.
    start_with_edit_view: Var[bool]

    # If true, it'll update the value onBlur and turn off the edit mode.
    submit_on_blur: Var[bool]

    # The value of the Editable in both edit & preview mode
    value: Var[str]

    # The initial value of the Editable in both edit and preview mode.
    default_value: Var[str]

    def get_controlled_triggers(self) -> Dict[str, Var]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            "on_change": EVENT_ARG,
            "on_edit": EVENT_ARG,
            "on_submit": EVENT_ARG,
            "on_cancel": EVENT_ARG,
        }


class EditableInput(ChakraComponent):
    """The edit view of the component. It shows when you click or focus on the text."""

    tag = "EditableInput"


class EditableTextarea(ChakraComponent):
    """Use the textarea element to handle multi line text input in an editable context."""

    tag = "EditableTextarea"


class EditablePreview(ChakraComponent):
    """The read-only view of the component."""

    tag = "EditablePreview"
