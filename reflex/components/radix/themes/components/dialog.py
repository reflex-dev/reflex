"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal, Optional

from reflex import el
from reflex.components.component import ComponentNamespace
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)


class DialogRoot(RadixThemesComponent):
    """Root component for Dialog."""

    tag: str = "Dialog.Root"

    # The controlled open state of the dialog.
    open: Optional[Var[bool]] = None

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_OPEN_CHANGE: lambda e0: [e0],
        }


class DialogTrigger(RadixThemesComponent):
    """Trigger an action or event, to open a Dialog modal."""

    tag: str = "Dialog.Trigger"


class DialogTitle(RadixThemesComponent):
    """Title component to display inside a Dialog modal."""

    tag: str = "Dialog.Title"


class DialogContent(el.Div, RadixThemesComponent):
    """Content component to display inside a Dialog modal."""

    tag: str = "Dialog.Content"

    # DialogContent size "1" - "4"
    size: Optional[Var[Literal["1", "2", "3", "4"]]] = None

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_OPEN_AUTO_FOCUS: lambda e0: [e0],
            EventTriggers.ON_CLOSE_AUTO_FOCUS: lambda e0: [e0],
            EventTriggers.ON_ESCAPE_KEY_DOWN: lambda e0: [e0],
            EventTriggers.ON_POINTER_DOWN_OUTSIDE: lambda e0: [e0],
            EventTriggers.ON_INTERACT_OUTSIDE: lambda e0: [e0],
        }


class DialogDescription(RadixThemesComponent):
    """Description component to display inside a Dialog modal."""

    tag: str = "Dialog.Description"


class DialogClose(RadixThemesComponent):
    """Close button component to close an open Dialog modal."""

    tag: str = "Dialog.Close"


class Dialog(ComponentNamespace):
    """Dialog components namespace."""

    root = __call__ = staticmethod(DialogRoot.create)
    trigger = staticmethod(DialogTrigger.create)
    title = staticmethod(DialogTitle.create)
    content = staticmethod(DialogContent.create)
    description = staticmethod(DialogDescription.create)
    close = staticmethod(DialogClose.create)


dialog = Dialog()
