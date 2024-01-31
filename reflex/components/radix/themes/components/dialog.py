"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex import el
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)


class DialogRoot(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Dialog.Root"

    # The controlled open state of the dialog.
    open: Var[bool]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_open_change": lambda e0: [e0],
        }


class DialogTrigger(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Dialog.Trigger"


class DialogTitle(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Dialog.Title"


class DialogContent(el.Div, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Dialog.Content"

    # DialogContent size "1" - "4"
    size: Var[Literal[1, 2, 3, 4]]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_open_auto_focus": lambda e0: [e0],
            "on_close_auto_focus": lambda e0: [e0],
            "on_escape_key_down": lambda e0: [e0],
            "on_pointer_down_outside": lambda e0: [e0],
            "on_interact_outside": lambda e0: [e0],
        }


class DialogDescription(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Dialog.Description"


class DialogClose(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Dialog.Close"
