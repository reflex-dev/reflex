"""Interactive components provided by @radix-ui/themes."""
from __future__ import annotations

from typing import Any, Dict, List, Literal

from reflex.components.component import Component, ComponentNamespace
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)


class TabsRoot(RadixThemesComponent):
    """Set of content sections to be displayed one at a time."""

    tag = "Tabs.Root"

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
    """Contains the triggers that sit alongside the active content."""

    tag = "Tabs.List"

    # Tabs size "1" - "2"
    size: Var[Literal["1", "2"]]


class TabsTrigger(RadixThemesComponent):
    """The button that activates its associated content."""

    tag = "Tabs.Trigger"

    # The value of the tab. Must be unique for each tab.
    value: Var[str]

    # Whether the tab is disabled
    disabled: Var[bool]

    # The color of the line under the tab when active.
    color_scheme: Var[LiteralAccentColor]

    _valid_parents: List[str] = ["TabsList"]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a TabsTrigger component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The TabsTrigger Component.
        """
        if "color_scheme" in props:
            custom_attrs = props.setdefault("custom_attrs", {})
            custom_attrs["data-accent-color"] = props["color_scheme"]
        return super().create(*children, **props)

    def _exclude_props(self) -> list[str]:
        return ["color_scheme"]


class TabsContent(RadixThemesComponent):
    """Contains the content associated with each trigger."""

    tag = "Tabs.Content"

    # The value of the tab. Must be unique for each tab.
    value: Var[str]


class Tabs(ComponentNamespace):
    """Set of content sections to be displayed one at a time."""

    root = __call__ = staticmethod(TabsRoot.create)
    list = staticmethod(TabsList.create)
    trigger = staticmethod(TabsTrigger.create)
    content = staticmethod(TabsContent.create)


tabs = Tabs()
