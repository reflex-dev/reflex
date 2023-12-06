"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex import el
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    RadixThemesComponent,
)

LiteralSwitchSize = Literal["1", "2", "3", "4"]


class AlertDialog(CommonMarginProps, RadixThemesComponent):
    """A toggle switch alternative to the checkbox."""

    tag = "AlertDialog.Root"

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


class AlertDialogTrigger(CommonMarginProps, RadixThemesComponent):
    """A toggle switch alternative to the checkbox."""

    tag = "AlertDialog.Trigger"


class AlertDialogContent(el.Div, CommonMarginProps, RadixThemesComponent):
    """A toggle switch alternative to the checkbox."""

    tag = "AlertDialog.Content"

    # Whether to force mount the content on open.
    force_mount: Var[bool]

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
        }


class AlertDialogTitle(CommonMarginProps, RadixThemesComponent):
    """A toggle switch alternative to the checkbox."""

    tag = "AlertDialog.Title"


class AlertDialogDescription(CommonMarginProps, RadixThemesComponent):
    """A toggle switch alternative to the checkbox."""

    tag = "AlertDialog.Description"
