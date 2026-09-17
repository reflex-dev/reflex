"""Interactive components provided by @radix-ui/themes."""

from typing import ClassVar, Literal

from reflex_base.components.component import ComponentNamespace, field
from reflex_base.constants.compiler import MemoizationMode
from reflex_base.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import (
    LiteralAccentColor,
    RadixThemesComponent,
    RadixThemesTriggerComponent,
)

LiteralDirType = Literal["ltr", "rtl"]

LiteralSizeType = Literal["1", "2"]

LiteralVariantType = Literal["solid", "soft"]

LiteralSideType = Literal["top", "right", "bottom", "left"]

LiteralAlignType = Literal["start", "center", "end"]

LiteralStickyType = Literal[
    "partial",
    "always",
]


class DropdownMenuRoot(RadixThemesComponent):
    """The Dropdown Menu Root Component."""

    tag = "DropdownMenu.Root"

    default_open: Var[bool] = field(
        doc="The open state of the dropdown menu when it is initially rendered. Use when you do not need to control its open state."
    )

    open: Var[bool] = field(
        doc="The controlled open state of the dropdown menu. Must be used in conjunction with onOpenChange."
    )

    modal: Var[bool] = field(
        doc="The modality of the dropdown menu. When set to true, interaction with outside elements will be disabled and only menu content will be visible to screen readers. Defaults to True."
    )

    dir: Var[LiteralDirType] = field(
        doc="The reading direction of submenus when applicable. If omitted, inherits globally from DirectionProvider or assumes LTR (left-to-right) reading mode."
    )

    _invalid_children: ClassVar[list[str]] = ["DropdownMenuItem"]

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the open state changes."
    )


class DropdownMenuTrigger(RadixThemesTriggerComponent):
    """The button that toggles the dropdown menu."""

    tag = "DropdownMenu.Trigger"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False."
    )

    _valid_parents: ClassVar[list[str]] = ["DropdownMenuRoot"]

    _invalid_children: ClassVar[list[str]] = ["DropdownMenuContent"]

    _memoization_mode = MemoizationMode(recursive=False)


class DropdownMenuContent(RadixThemesComponent):
    """The Dropdown Menu Content component that pops out when the dropdown menu is open."""

    tag = "DropdownMenu.Content"

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
        doc="Fired when the dialog is closed."
    )

    on_escape_key_down: EventHandler[no_args_event_spec] = field(
        doc="Fired when the escape key is pressed."
    )

    on_pointer_down_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer is down outside the dialog."
    )

    on_focus_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when focus moves outside the dialog."
    )

    on_interact_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer interacts outside the dialog."
    )


class DropdownMenuSubTrigger(RadixThemesTriggerComponent):
    """An item that opens a submenu."""

    tag = "DropdownMenu.SubTrigger"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False."
    )

    disabled: Var[bool] = field(
        doc="When true, prevents the user from interacting with the item."
    )

    text_value: Var[str] = field(
        doc="Optional text used for typeahead purposes. By default the typeahead behavior will use the .textContent of the item. Use this when the content is complex, or you have non-textual content inside."
    )

    _valid_parents: ClassVar[list[str]] = ["DropdownMenuContent", "DropdownMenuSub"]

    _memoization_mode = MemoizationMode(recursive=False)


class DropdownMenuSub(RadixThemesComponent):
    """Contains all the parts of a submenu."""

    tag = "DropdownMenu.Sub"

    open: Var[bool] = field(
        doc="The controlled open state of the submenu. Must be used in conjunction with `on_open_change`."
    )

    default_open: Var[bool] = field(
        doc="The open state of the submenu when it is initially rendered. Use when you do not need to control its open state."
    )

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the open state changes."
    )


class DropdownMenuSubContent(RadixThemesComponent):
    """The component that pops out when a submenu is open. Must be rendered inside DropdownMenuSub."""

    tag = "DropdownMenu.SubContent"

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

    _valid_parents: ClassVar[list[str]] = ["DropdownMenuSub"]

    on_escape_key_down: EventHandler[no_args_event_spec] = field(
        doc="Fired when the escape key is pressed."
    )

    on_pointer_down_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer is down outside the dialog."
    )

    on_focus_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when focus moves outside the dialog."
    )

    on_interact_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer interacts outside the dialog."
    )


class DropdownMenuItem(RadixThemesComponent):
    """The Dropdown Menu Item Component."""

    tag = "DropdownMenu.Item"

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Override theme color for Dropdown Menu Item"
    )

    shortcut: Var[str] = field(doc="Shortcut to render a menu item as a link")

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False."
    )

    disabled: Var[bool] = field(
        doc="When true, prevents the user from interacting with the item."
    )

    text_value: Var[str] = field(
        doc="Optional text used for typeahead purposes. By default the typeahead behavior will use the .textContent of the item. Use this when the content is complex, or you have non-textual content inside."
    )

    _valid_parents: ClassVar[list[str]] = [
        "DropdownMenuContent",
        "DropdownMenuSubContent",
    ]

    on_select: EventHandler[no_args_event_spec] = field(
        doc="Fired when the item is selected."
    )


class DropdownMenuSeparator(RadixThemesComponent):
    """Dropdown Menu Separator Component. Used to visually separate items in the dropdown menu."""

    tag = "DropdownMenu.Separator"


class DropdownMenu(ComponentNamespace):
    """DropdownMenu components namespace."""

    root = staticmethod(DropdownMenuRoot.create)
    trigger = staticmethod(DropdownMenuTrigger.create)
    content = staticmethod(DropdownMenuContent.create)
    sub_trigger = staticmethod(DropdownMenuSubTrigger.create)
    sub = staticmethod(DropdownMenuSub.create)
    sub_content = staticmethod(DropdownMenuSubContent.create)
    item = staticmethod(DropdownMenuItem.create)
    separator = staticmethod(DropdownMenuSeparator.create)


menu = dropdown_menu = DropdownMenu()
