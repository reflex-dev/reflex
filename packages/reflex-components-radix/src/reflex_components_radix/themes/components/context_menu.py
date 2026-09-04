"""Interactive components provided by @radix-ui/themes."""

from typing import ClassVar, Literal

from reflex_base.components.component import ComponentNamespace, field
from reflex_base.constants.compiler import MemoizationMode
from reflex_base.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent

from .checkbox import Checkbox
from .radio_group import HighLevelRadioGroup

LiteralDirType = Literal["ltr", "rtl"]

LiteralSizeType = Literal["1", "2"]

LiteralVariantType = Literal["solid", "soft"]

LiteralSideType = Literal["top", "right", "bottom", "left"]

LiteralAlignType = Literal["start", "center", "end"]

LiteralStickyType = Literal[
    "partial",
    "always",
]


class ContextMenuRoot(RadixThemesComponent):
    """Menu representing a set of actions, displayed at the origin of a pointer right-click or long-press."""

    tag = "ContextMenu.Root"

    modal: Var[bool] = field(
        doc="The modality of the context menu. When set to true, interaction with outside elements will be disabled and only menu content will be visible to screen readers."
    )

    _invalid_children: ClassVar[list[str]] = ["ContextMenuItem"]

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the open state changes."
    )

    dir: Var[LiteralDirType] = field(
        doc="The reading direction of submenus when applicable. If omitted, inherits globally from DirectionProvider or assumes LTR (left-to-right) reading mode."
    )


class ContextMenuTrigger(RadixThemesComponent):
    """Wraps the element that will open the context menu."""

    tag = "ContextMenu.Trigger"

    disabled: Var[bool] = field(doc="Whether the trigger is disabled")

    _valid_parents: ClassVar[list[str]] = ["ContextMenuRoot"]

    _invalid_children: ClassVar[list[str]] = ["ContextMenuContent"]

    _memoization_mode = MemoizationMode(recursive=False)


class ContextMenuContent(RadixThemesComponent):
    """The component that pops out when the context menu is open."""

    tag = "ContextMenu.Content"

    size: Var[Responsive[LiteralSizeType]] = field(
        doc='Dropdown Menu Content size "1" - "2"'
    )

    variant: Var[LiteralVariantType] = field(
        doc='Variant of Dropdown Menu Content: "solid" | "soft"'
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Override theme color for Dropdown Menu Content"
    )

    high_contrast: Var[bool] = field(
        doc="Renders the Dropdown Menu Content in higher contrast"
    )

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False."
    )

    loop: Var[bool] = field(
        doc="When True, keyboard navigation will loop from last item to first, and vice versa. Defaults to False."
    )

    force_mount: Var[bool] = field(
        doc="Used to force mounting when more control is needed. Useful when controlling animation with React animation libraries."
    )

    side: Var[LiteralSideType] = field(
        doc='The preferred side of the trigger to render against when open. Will be reversed when collisions occur and `avoid_collisions` is enabled.The position of the tooltip. Defaults to "top".'
    )

    side_offset: Var[float | int] = field(
        doc="The distance in pixels from the trigger. Defaults to 0."
    )

    align: Var[LiteralAlignType] = field(
        doc='The preferred alignment against the trigger. May change when collisions occur. Defaults to "center".'
    )

    align_offset: Var[float | int] = field(
        doc='An offset in pixels from the "start" or "end" alignment options.'
    )

    avoid_collisions: Var[bool] = field(
        doc="When true, overrides the side and align preferences to prevent collisions with boundary edges. Defaults to True."
    )

    collision_padding: Var[float | int | dict[str, float | int]] = field(
        doc='The distance in pixels from the boundary edges where collision detection should occur. Accepts a number (same for all sides), or a partial padding object, for example: { "top": 20, "left": 20 }. Defaults to 0.'
    )

    sticky: Var[LiteralStickyType] = field(
        doc='The sticky behavior on the align axis. "partial" will keep the content in the boundary as long as the trigger is at least partially in the boundary whilst "always" will keep the content in the boundary regardless. Defaults to "partial".'
    )

    hide_when_detached: Var[bool] = field(
        doc="Whether to hide the content when the trigger becomes fully occluded. Defaults to False."
    )

    on_close_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when focus moves back after closing."
    )

    on_escape_key_down: EventHandler[no_args_event_spec] = field(
        doc="Fired when the escape key is pressed."
    )

    on_pointer_down_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when a pointer down event happens outside the context menu."
    )

    on_focus_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when focus moves outside the context menu."
    )

    on_interact_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer interacts outside the context menu."
    )


class ContextMenuSub(RadixThemesComponent):
    """Contains all the parts of a submenu."""

    tag = "ContextMenu.Sub"

    open: Var[bool] = field(
        doc="The controlled open state of the submenu. Must be used in conjunction with `on_open_change`."
    )

    default_open: Var[bool] = field(
        doc="The open state of the submenu when it is initially rendered. Use when you do not need to control its open state."
    )

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the open state changes."
    )


class ContextMenuSubTrigger(RadixThemesComponent):
    """An item that opens a submenu."""

    tag = "ContextMenu.SubTrigger"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False."
    )

    disabled: Var[bool] = field(doc="Whether the trigger is disabled")

    text_value: Var[str] = field(
        doc="Optional text used for typeahead purposes. By default the typeahead behavior will use the .textContent of the item. Use this when the content is complex, or you have non-textual content inside."
    )

    _valid_parents: ClassVar[list[str]] = ["ContextMenuContent", "ContextMenuSub"]

    _memoization_mode = MemoizationMode(recursive=False)


class ContextMenuSubContent(RadixThemesComponent):
    """The component that pops out when a submenu is open."""

    tag = "ContextMenu.SubContent"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False."
    )

    loop: Var[bool] = field(
        doc="When True, keyboard navigation will loop from last item to first, and vice versa. Defaults to False."
    )

    force_mount: Var[bool] = field(
        doc="Used to force mounting when more control is needed. Useful when controlling animation with React animation libraries."
    )

    side_offset: Var[float | int] = field(
        doc="The distance in pixels from the trigger. Defaults to 0."
    )

    align_offset: Var[float | int] = field(
        doc='An offset in pixels from the "start" or "end" alignment options.'
    )

    avoid_collisions: Var[bool] = field(
        doc="When true, overrides the side and align preferences to prevent collisions with boundary edges. Defaults to True."
    )

    collision_padding: Var[float | int | dict[str, float | int]] = field(
        doc='The distance in pixels from the boundary edges where collision detection should occur. Accepts a number (same for all sides), or a partial padding object, for example: { "top": 20, "left": 20 }. Defaults to 0.'
    )

    sticky: Var[LiteralStickyType] = field(
        doc='The sticky behavior on the align axis. "partial" will keep the content in the boundary as long as the trigger is at least partially in the boundary whilst "always" will keep the content in the boundary regardless. Defaults to "partial".'
    )

    hide_when_detached: Var[bool] = field(
        doc="Whether to hide the content when the trigger becomes fully occluded. Defaults to False."
    )

    _valid_parents: ClassVar[list[str]] = ["ContextMenuSub"]

    on_escape_key_down: EventHandler[no_args_event_spec] = field(
        doc="Fired when the escape key is pressed."
    )

    on_pointer_down_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when a pointer down event happens outside the context menu."
    )

    on_focus_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when focus moves outside the context menu."
    )

    on_interact_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when interacting outside the context menu."
    )


class ContextMenuItem(RadixThemesComponent):
    """The component that contains the context menu items."""

    tag = "ContextMenu.Item"

    color_scheme: Var[LiteralAccentColor] = field(doc="Override theme color for button")

    shortcut: Var[str] = field(doc="Shortcut to render a menu item as a link")

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False."
    )

    disabled: Var[bool] = field(
        doc="When true, prevents the user from interacting with the item."
    )

    text_value: Var[str] = field(
        doc="Optional text used for typeahead purposes. By default the typeahead behavior will use the content of the item. Use this when the content is complex, or you have non-textual content inside."
    )

    _valid_parents: ClassVar[list[str]] = [
        "ContextMenuContent",
        "ContextMenuSubContent",
        "ContextMenuGroup",
    ]

    on_select: EventHandler[no_args_event_spec] = field(
        doc="Fired when the item is selected."
    )


class ContextMenuSeparator(RadixThemesComponent):
    """Separates items in a context menu."""

    tag = "ContextMenu.Separator"


class ContextMenuCheckbox(Checkbox):
    """The component that contains the checkbox."""

    tag = "ContextMenu.CheckboxItem"

    shortcut: Var[str] = field(doc="Text to render as shortcut.")


class ContextMenuLabel(RadixThemesComponent):
    """The component that contains the label."""

    tag = "ContextMenu.Label"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False."
    )


class ContextMenuGroup(RadixThemesComponent):
    """The component that contains the group."""

    tag = "ContextMenu.Group"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False."
    )

    _valid_parents: ClassVar[list[str]] = [
        "ContextMenuContent",
        "ContextMenuSubContent",
    ]


class ContextMenuRadioGroup(RadixThemesComponent):
    """The component that contains context menu radio items."""

    tag = "ContextMenu.RadioGroup"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False."
    )

    value: Var[str] = field(doc="The value of the selected item in the group.")

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    on_change: EventHandler[passthrough_event_spec(str)] = field(
        doc="Fired when the value of the radio group changes."
    )

    _valid_parents: ClassVar[list[str]] = [
        "ContextMenuRadioItem",
        "ContextMenuSubContent",
        "ContextMenuContent",
        "ContextMenuSub",
    ]


class ContextMenuRadioItem(HighLevelRadioGroup):
    """The component that contains context menu radio items."""

    tag = "ContextMenu.RadioItem"

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Override theme color for Dropdown Menu Content"
    )

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False."
    )

    value: Var[str] = field(doc="The unique value of the item.")

    disabled: Var[bool] = field(
        doc="When true, prevents the user from interacting with the item."
    )

    on_select: EventHandler[no_args_event_spec] = field(
        doc="Event handler called when the user selects an item (via mouse or keyboard). Calling event.preventDefault in this handler will prevent the context menu from closing when selecting that item."
    )

    text_value: Var[str] = field(
        doc="Optional text used for typeahead purposes. By default the typeahead behavior will use the .textContent of the item. Use this when the content is complex, or you have non-textual content inside."
    )


class ContextMenu(ComponentNamespace):
    """Menu representing a set of actions, displayed at the origin of a pointer right-click or long-press."""

    root = staticmethod(ContextMenuRoot.create)
    trigger = staticmethod(ContextMenuTrigger.create)
    content = staticmethod(ContextMenuContent.create)
    sub = staticmethod(ContextMenuSub.create)
    sub_trigger = staticmethod(ContextMenuSubTrigger.create)
    sub_content = staticmethod(ContextMenuSubContent.create)
    item = staticmethod(ContextMenuItem.create)
    separator = staticmethod(ContextMenuSeparator.create)
    checkbox = staticmethod(ContextMenuCheckbox.create)
    label = staticmethod(ContextMenuLabel.create)
    group = staticmethod(ContextMenuGroup.create)
    radio_group = staticmethod(ContextMenuRadioGroup.create)
    radio = staticmethod(ContextMenuRadioItem.create)


context_menu = ContextMenu()
