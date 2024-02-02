"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)


class TabsRoot(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Tabs.Root"

    # The variant of the tab
    variant: Var[Literal["surface", "ghost"]]

    # The value of the tab that should be active when initially rendered. Use when you do not need to control the state of the tabs.
    default_value: Var[str]

    # The controlled value of the tab that should be active. Use when you need to control the state of the tabs.
    value: Var[str]

    # The orientation of the tabs.
    orientation: Var[Literal["horizontal", "vertical"]]

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: lambda e0: [e0],
        }


class TabsList(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Tabs.List"


class TabsTrigger(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Tabs.Trigger"

    # The value of the tab. Must be unique for each tab.
    value: Var[str]

    # Whether the tab is disabled
    disabled: Var[bool]


class TabsContent(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Tabs.Content"

    # The value of the tab. Must be unique for each tab.
    value: Var[str]
