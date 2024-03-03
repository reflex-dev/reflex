"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, List, Literal, Union

import reflex as rx
from reflex.components.component import Component, ComponentNamespace
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)


class SelectRoot(RadixThemesComponent):
    """Displays a list of options for the user to pick from, triggered by a button."""

    tag = "Select.Root"

    # The size of the select: "1" | "2" | "3"
    size: Var[Literal["1", "2", "3"]]

    # The value of the select when initially rendered. Use when you do not need to control the state of the select.
    default_value: Var[str]

    # The controlled value of the select. Should be used in conjunction with on_change.
    value: Var[str]

    # The open state of the select when it is initially rendered. Use when you do not need to control its open state.
    default_open: Var[bool]

    # The controlled open state of the select. Must be used in conjunction with on_open_change.
    open: Var[bool]

    # The name of the select control when submitting the form.
    name: Var[str]

    # When True, prevents the user from interacting with select.
    disabled: Var[bool]

    # When True, indicates that the user must select a value before the owning form can be submitted.
    required: Var[bool]

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_OPEN_CHANGE: lambda e0: [e0],
            EventTriggers.ON_CHANGE: lambda e0: [e0],
        }


class SelectTrigger(RadixThemesComponent):
    """The button that toggles the select."""

    tag = "Select.Trigger"

    # Variant of the select trigger
    variant: Var[Literal["classic", "surface", "soft", "ghost"]]

    # The color of the select trigger
    color_scheme: Var[LiteralAccentColor]

    # The radius of the select trigger
    radius: Var[LiteralRadius]

    # The placeholder of the select trigger
    placeholder: Var[str]

    _valid_parents: List[str] = ["SelectRoot"]


class SelectContent(RadixThemesComponent):
    """The component that pops out when the select is open."""

    tag = "Select.Content"

    # The variant of the select content
    variant: Var[Literal["solid", "soft"]]

    # The color of the select content
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the select content with higher contrast color against background
    high_contrast: Var[bool]

    # The positioning mode to use, item-aligned is the default and behaves similarly to a native MacOS menu by positioning content relative to the active item. popper positions content in the same way as our other primitives, for example Popover or DropdownMenu.
    position: Var[Literal["item-aligned", "popper"]]

    # The preferred side of the anchor to render against when open. Will be reversed when collisions occur and avoidCollisions is enabled. Only available when position is set to popper.
    side: Var[Literal["top", "right", "bottom", "left"]]

    # The distance in pixels from the anchor. Only available when position is set to popper.
    side_offset: Var[int]

    # The preferred alignment against the anchor. May change when collisions occur. Only available when position is set to popper.
    align: Var[Literal["start", "center", "end"]]

    # The vertical distance in pixels from the anchor. Only available when position is set to popper.
    align_offset: Var[int]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CLOSE_AUTO_FOCUS: lambda e0: [e0],
            EventTriggers.ON_ESCAPE_KEY_DOWN: lambda e0: [e0],
            EventTriggers.ON_POINTER_DOWN_OUTSIDE: lambda e0: [e0],
        }


class SelectGroup(RadixThemesComponent):
    """Used to group multiple items."""

    tag = "Select.Group"

    _valid_parents: List[str] = ["SelectContent"]


class SelectItem(RadixThemesComponent):
    """The component that contains the select items."""

    tag = "Select.Item"

    # The value given as data when submitting a form with a name.
    value: Var[str]

    # Whether the select item is disabled
    disabled: Var[bool]

    _valid_parents: List[str] = ["SelectGroup", "SelectContent"]


class SelectLabel(RadixThemesComponent):
    """Used to render the label of a group, it isn't focusable using arrow keys."""

    tag = "Select.Label"

    _valid_parents: List[str] = ["SelectGroup"]


class SelectSeparator(RadixThemesComponent):
    """Used to visually separate items in the Select."""

    tag = "Select.Separator"


class HighLevelSelect(SelectRoot):
    """High level wrapper for the Select component."""

    # The items of the select.
    items: Var[List[str]]

    # The placeholder of the select.
    placeholder: Var[str]

    # The label of the select.
    label: Var[str]

    # The color of the select.
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the select with higher contrast color against background.
    high_contrast: Var[bool]

    # The variant of the select.
    variant: Var[Literal["classic", "surface", "soft", "ghost"]]

    # The radius of the select.
    radius: Var[LiteralRadius]

    # The width of the select.
    width: Var[str]

    @classmethod
    def create(cls, items: Union[List[str], Var[List[str]]], **props) -> Component:
        """Create a select component.

        Args:
            items: The items of the select.
            **props: Additional properties to apply to the select component.

        Returns:
            The select component.
        """
        content_props = {
            prop: props.pop(prop) for prop in ["high_contrast"] if prop in props
        }

        trigger_props = {
            prop: props.pop(prop)
            for prop in ["placeholder", "variant", "radius", "width"]
            if prop in props
        }

        color_scheme = props.pop("color_scheme", None)

        if color_scheme is not None:
            content_props["color_scheme"] = color_scheme
            trigger_props["color_scheme"] = color_scheme

        label = props.pop("label", None)

        if isinstance(items, Var):
            child = [
                rx.foreach(items, lambda item: SelectItem.create(item, value=item))
            ]
        else:
            child = [SelectItem.create(item, value=item) for item in items]

        return SelectRoot.create(
            SelectTrigger.create(
                **trigger_props,
            ),
            SelectContent.create(
                SelectGroup.create(
                    SelectLabel.create(label) if label is not None else "",
                    *child,
                ),
                **content_props,
            ),
            **props,
        )


class Select(ComponentNamespace):
    """Select components namespace."""

    root = staticmethod(SelectRoot.create)
    trigger = staticmethod(SelectTrigger.create)
    content = staticmethod(SelectContent.create)
    group = staticmethod(SelectGroup.create)
    item = staticmethod(SelectItem.create)
    separator = staticmethod(SelectSeparator.create)
    label = staticmethod(SelectLabel.create)
    __call__ = staticmethod(HighLevelSelect.create)


select = Select()
