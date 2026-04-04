"""Interactive components provided by @radix-ui/themes."""

from collections.abc import Sequence
from typing import ClassVar, Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.constants.compiler import MemoizationMode
from reflex_base.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.foreach import foreach

from reflex_components_radix.themes.base import (
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)


class SelectRoot(RadixThemesComponent):
    """Displays a list of options for the user to pick from, triggered by a button."""

    tag = "Select.Root"

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        doc='The size of the select: "1" | "2" | "3"'
    )

    default_value: Var[str] = field(
        doc="The value of the select when initially rendered. Use when you do not need to control the state of the select."
    )

    value: Var[str] = field(
        doc="The controlled value of the select. Should be used in conjunction with on_change."
    )

    default_open: Var[bool] = field(
        doc="The open state of the select when it is initially rendered. Use when you do not need to control its open state."
    )

    open: Var[bool] = field(
        doc="The controlled open state of the select. Must be used in conjunction with on_open_change."
    )

    name: Var[str] = field(
        doc="The name of the select control when submitting the form."
    )

    disabled: Var[bool] = field(
        doc="When True, prevents the user from interacting with select."
    )

    required: Var[bool] = field(
        doc="When True, indicates that the user must select a value before the owning form can be submitted."
    )

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    on_change: EventHandler[passthrough_event_spec(str)] = field(
        doc="Fired when the value of the select changes."
    )

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the select is opened or closed."
    )


class SelectTrigger(RadixThemesComponent):
    """The button that toggles the select."""

    tag = "Select.Trigger"

    variant: Var[Literal["classic", "surface", "soft", "ghost"]] = field(
        doc="Variant of the select trigger"
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="The color of the select trigger")

    radius: Var[LiteralRadius] = field(doc="The radius of the select trigger")

    placeholder: Var[str] = field(doc="The placeholder of the select trigger")

    _valid_parents: ClassVar[list[str]] = ["SelectRoot"]

    _memoization_mode = MemoizationMode(recursive=False)


class SelectContent(RadixThemesComponent):
    """The component that pops out when the select is open."""

    tag = "Select.Content"

    variant: Var[Literal["solid", "soft"]] = field(
        doc="The variant of the select content"
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="The color of the select content")

    high_contrast: Var[bool] = field(
        doc="Whether to render the select content with higher contrast color against background"
    )

    position: Var[Literal["item-aligned", "popper"]] = field(
        doc="The positioning mode to use, item-aligned is the default and behaves similarly to a native MacOS menu by positioning content relative to the active item. popper positions content in the same way as our other primitives, for example Popover or DropdownMenu."
    )

    side: Var[Literal["top", "right", "bottom", "left"]] = field(
        doc="The preferred side of the anchor to render against when open. Will be reversed when collisions occur and avoidCollisions is enabled. Only available when position is set to popper."
    )

    side_offset: Var[int] = field(
        doc="The distance in pixels from the anchor. Only available when position is set to popper."
    )

    align: Var[Literal["start", "center", "end"]] = field(
        doc="The preferred alignment against the anchor. May change when collisions occur. Only available when position is set to popper."
    )

    align_offset: Var[int] = field(
        doc="The vertical distance in pixels from the anchor. Only available when position is set to popper."
    )

    on_close_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the select content is closed."
    )

    on_escape_key_down: EventHandler[no_args_event_spec] = field(
        doc="Fired when the escape key is pressed."
    )

    on_pointer_down_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when a pointer down event happens outside the select content."
    )


class SelectGroup(RadixThemesComponent):
    """Used to group multiple items."""

    tag = "Select.Group"

    _valid_parents: ClassVar[list[str]] = ["SelectContent"]


class SelectItem(RadixThemesComponent):
    """The component that contains the select items."""

    tag = "Select.Item"

    value: Var[str] = field(
        doc="The value given as data when submitting a form with a name."
    )

    disabled: Var[bool] = field(doc="Whether the select item is disabled")

    _valid_parents: ClassVar[list[str]] = ["SelectGroup", "SelectContent"]


class SelectLabel(RadixThemesComponent):
    """Used to render the label of a group, it isn't focusable using arrow keys."""

    tag = "Select.Label"

    _valid_parents: ClassVar[list[str]] = ["SelectGroup"]


class SelectSeparator(RadixThemesComponent):
    """Used to visually separate items in the Select."""

    tag = "Select.Separator"


class HighLevelSelect(SelectRoot):
    """High level wrapper for the Select component."""

    items: Var[Sequence[str]] = field(doc="The items of the select.")

    placeholder: Var[str] = field(doc="The placeholder of the select.")

    label: Var[str] = field(doc="The label of the select.")

    color_scheme: Var[LiteralAccentColor] = field(doc="The color of the select.")

    high_contrast: Var[bool] = field(
        doc="Whether to render the select with higher contrast color against background."
    )

    variant: Var[Literal["classic", "surface", "soft", "ghost"]] = field(
        doc="The variant of the select."
    )

    radius: Var[LiteralRadius] = field(doc="The radius of the select.")

    width: Var[str] = field(doc="The width of the select.")

    position: Var[Literal["item-aligned", "popper"]] = field(
        doc='The positioning mode to use. Default is "item-aligned".'
    )

    @classmethod
    def create(cls, items: list[str] | Var[list[str]], **props) -> Component:
        """Create a select component.

        Args:
            items: The items of the select.
            **props: Additional properties to apply to the select component.

        Returns:
            The select component.
        """
        trigger_prop_list = [
            "id",
            "placeholder",
            "variant",
            "radius",
            "width",
            "flex_shrink",
            "custom_attrs",
        ]

        content_props = {
            prop: props.pop(prop)
            for prop in ["high_contrast", "position"]
            if prop in props
        }

        trigger_props = {
            prop: props.pop(prop) for prop in trigger_prop_list if prop in props
        }

        color_scheme = props.pop("color_scheme", None)

        if color_scheme is not None:
            content_props["color_scheme"] = color_scheme
            trigger_props["color_scheme"] = color_scheme

        label = props.pop("label", None)

        if isinstance(items, Var):
            child = [foreach(items, lambda item: SelectItem.create(item, value=item))]
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
