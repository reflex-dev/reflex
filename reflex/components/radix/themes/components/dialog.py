"""Interactive components provided by @radix-ui/themes."""

from typing import Any, Dict, Literal

from reflex import el
from reflex.components.component import Component, ComponentNamespace
from reflex.components.radix.themes.layout.flex import Flex
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)


class DialogRoot(RadixThemesComponent):
    """Root component for Dialog."""

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
            EventTriggers.ON_OPEN_CHANGE: lambda e0: [e0],
        }


class DialogTrigger(RadixThemesComponent):
    """Trigger an action or event, to open a Dialog modal."""

    tag = "Dialog.Trigger"


class DialogTitle(RadixThemesComponent):
    """Title component to display inside a Dialog modal."""

    tag = "Dialog.Title"


class DialogContent(el.Div, RadixThemesComponent):
    """Content component to display inside a Dialog modal."""

    tag = "Dialog.Content"

    # DialogContent size "1" - "4"
    size: Var[Literal["1", "2", "3", "4"]]

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

    tag = "Dialog.Description"


class DialogClose(RadixThemesComponent):
    """Close button component to close an open Dialog modal."""

    tag = "Dialog.Close"

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a new DialogClose instance.

        Args:
            children: The children of the element.
            props: The properties of the element.

        Returns:
            The new DialogClose instance.
        """
        for child in children:
            if "on_click" in getattr(child, "event_triggers", {}):
                children = (Flex.create(*children),)
                break
        return super().create(*children, **props)


class Dialog(ComponentNamespace):
    """Dialog components namespace."""

    root = __call__ = staticmethod(DialogRoot.create)
    trigger = staticmethod(DialogTrigger.create)
    title = staticmethod(DialogTitle.create)
    content = staticmethod(DialogContent.create)
    description = staticmethod(DialogDescription.create)
    close = staticmethod(DialogClose.create)


dialog = Dialog()
