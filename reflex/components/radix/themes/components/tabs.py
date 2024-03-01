"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, List, Literal, Optional

from reflex.components.component import ComponentNamespace
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)


class TabsRoot(RadixThemesComponent):
    """Set of content sections to be displayed one at a time."""

    tag: str = "Tabs.Root"

    # The value of the tab that should be active when initially rendered. Use when you do not need to control the state of the tabs.
    default_value: Optional[Var[str]] = None

    # The controlled value of the tab that should be active. Use when you need to control the state of the tabs.
    value: Optional[Var[str]] = None

    # The orientation of the tabs.
    orientation: Optional[Var[Literal["horizontal", "vertical"]]] = None

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
    """Contains the triggers that sit alongside the active content."""

    tag: str = "Tabs.List"

    # Tabs size "1" - "2"
    size: Optional[Var[Literal["1", "2"]]] = None


class TabsTrigger(RadixThemesComponent):
    """The button that activates its associated content."""

    tag: str = "Tabs.Trigger"

    # The value of the tab. Must be unique for each tab.
    value: Optional[Var[str]] = None

    # Whether the tab is disabled
    disabled: Optional[Var[bool]] = None

    _valid_parents: List[str] = ["TabsList"]


class TabsContent(RadixThemesComponent):
    """Contains the content associated with each trigger."""

    tag: str = "Tabs.Content"

    # The value of the tab. Must be unique for each tab.
    value: Optional[Var[str]] = None


class Tabs(ComponentNamespace):
    """Set of content sections to be displayed one at a time."""

    root = __call__ = staticmethod(TabsRoot.create)
    list = staticmethod(TabsList.create)
    trigger = staticmethod(TabsTrigger.create)
    content = staticmethod(TabsContent.create)


tabs = Tabs()
