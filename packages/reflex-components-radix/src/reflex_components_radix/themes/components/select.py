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
        doc='The size of the select trigger. Default is "2". Use "1" for dense forms or tables, "3" for prominent calls-to-action.'
    )

    default_value: Var[str] = field(
        doc="The initial value of the select when the component first renders. Use this for uncontrolled selects where you don't need to track changes in state. Should match one of the values in the options list."
    )

    value: Var[str] = field(
        doc="The controlled value of the select. When provided, the component becomes controlled and must be updated via an on_change handler. For uncontrolled usage where you just need an initial value, use default_value instead."
    )

    default_open: Var[bool] = field(
        doc="Whether the dropdown menu is initially open (uncontrolled). Most apps don't need to set this — the dropdown opens on user interaction automatically."
    )

    open: Var[bool] = field(
        doc="Whether the dropdown menu is currently open (controlled). Must be used in conjunction with on_open_change. Most apps don't need to set this — the dropdown opens on user interaction automatically."
    )

    name: Var[str] = field(
        doc="The name used to identify this field when the select is submitted as part of a form. If omitted, the select's value will not be included in form data."
    )

    disabled: Var[bool] = field(
        doc="When True, the user cannot interact with the select. Default is False. To disable individual options, use the low-level API and set disabled on specific items."
    )

    required: Var[bool] = field(
        doc="When True and used within a form, the form cannot be submitted until the user selects a value. Default is False."
    )

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    on_change: EventHandler[passthrough_event_spec(str)] = field(
        doc="Event handler called when the user selects a different option. Receives the new value as a string."
    )

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Event handler called when the dropdown opens or closes. Receives a boolean indicating the open state."
    )


class SelectTrigger(RadixThemesComponent):
    """The button that toggles the select."""

    tag = "Select.Trigger"

    variant: Var[Literal["classic", "surface", "soft", "ghost"]] = field(
        doc='Visual style of the select trigger. Options are "classic" (bordered), "surface" (filled), "soft" (subtle elevation), or "ghost" (minimal chrome).'
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Override the default accent color of the select trigger. Accepts any Reflex color token."
    )

    radius: Var[LiteralRadius] = field(
        doc='Border radius of the select trigger. Inherits from theme by default. Accepts "none", "small", "medium", "large", or "full".'
    )

    placeholder: Var[str] = field(
        doc="Text displayed when no option is selected. If value or default_value is set, the placeholder is hidden."
    )

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
        doc='Controls how the dropdown menu positions relative to the trigger. Default is "item-aligned" (behaves like a native macOS menu by positioning content relative to the active item). Use "popper" when placing a select inside a Drawer, Dialog, or other portal-based container.'
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
        doc="The value submitted with form data when this item is selected. Must be unique within the select."
    )

    disabled: Var[bool] = field(
        doc="When True, this specific item cannot be selected. The item is still visible but appears muted and is skipped by keyboard navigation."
    )

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

    items: Var[Sequence[str]] = field(
        doc="The list of option strings to display. Each string becomes one selectable item in the dropdown."
    )

    placeholder: Var[str] = field(
        doc="Text displayed when no option is selected. If value or default_value is set, the placeholder is hidden."
    )

    label: Var[str] = field(
        doc="An optional group heading rendered inside the dropdown above the items. Purely visual — does not affect form submission."
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Override the default accent color. Accepts any Reflex color token."
    )

    high_contrast: Var[bool] = field(
        doc="When True, the select content renders with higher contrast against the background."
    )

    variant: Var[Literal["classic", "surface", "soft", "ghost"]] = field(
        doc='Visual style of the select. Options are "classic" (bordered), "surface" (filled), "soft" (subtle elevation), or "ghost" (minimal chrome).'
    )

    radius: Var[LiteralRadius] = field(
        doc='Border radius. Inherits from theme by default. Accepts "none", "small", "medium", "large", or "full".'
    )

    width: Var[str] = field(
        doc="Explicit CSS width for the select trigger (e.g. '200px', '100%'). Inherits from parent layout by default."
    )

    position: Var[Literal["item-aligned", "popper"]] = field(
        doc='Controls how the dropdown menu positions relative to the trigger. Default is "item-aligned". Use "popper" when placing a select inside a Drawer, Dialog, or other portal-based container.'
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
