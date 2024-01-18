"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, List, Literal, Union

import reflex as rx
from reflex.components.radix.themes.layout.box import Box
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    RadixThemesComponent,
)


class TabsRoot(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Tabs.Root"

    # The variant of the tab
    variant: Var[Literal["surface", "ghost"]]

    # The value of the tab that should be active when initially rendered. Use when you do not need to control the state of the tabs.
    default_value: Var[str]

    # The controlled value of the tab that should be active. Use when you need to control the state of the tabs.
    value: Var[str]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_value_change": lambda e0: [e0],
        }


class TabsList(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Tabs.List"


class TabsTrigger(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Tabs.Trigger"

    # The value of the tab. Must be unique for each tab.
    value: Var[str]

    # Whether the tab is disabled
    disabled: Var[bool]


class TabsContent(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Tabs.Content"

    # The value of the tab. Must be unique for each tab.
    value: Var[str]


class Tabs(TabsRoot):
    """High level component to render a Tabs component."""

    # The labels of the tabs.
    labels: Var[List[str]]

    # The content to render.
    contents: List[rx.Component]

    @classmethod
    def create(
        cls,
        labels: Union[List[str], Var[List[str]]],
        contents: Union[Var[List[str]], List[rx.Component]],
        **props
    ) -> rx.Component:
        """Create a Tabs component.

        Args:
            labels: The labels of the tabs.
            contents: The contents of the tabs.
            **props: The properties of the component.

        Returns:
            The component.
        """
        labels2 = Var.create_safe(labels).to(list[str])
        contents = (
            [
                rx.foreach(
                    contents,
                    lambda content, i: TabsContent.create(content, value=labels[i]),
                )
            ]
            if isinstance(contents, Var)
            else [
                TabsContent.create(content, value=labels[i])
                for i, content in enumerate(contents)
            ]
        )

        print(str(contents[0]))
        return TabsRoot.create(
            TabsList.create(
                rx.foreach(
                    labels2,
                    lambda label: TabsTrigger.create(label, value=label),
                ),
            ),
            Box.create(
                *contents,
                px="4",
                pt="3",
                pb="2",
            ),
            **props,
        )


tabs = Tabs.create
