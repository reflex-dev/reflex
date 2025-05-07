"""Interactive components provided by @radix-ui/themes."""

from typing import ClassVar, Literal

from reflex.components.component import ComponentNamespace
from reflex.components.core.breakpoints import Responsive
from reflex.constants.compiler import MemoizationMode
from reflex.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex.vars.base import Var

from ..base import LiteralAccentColor, RadixThemesComponent
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

    # The modality of the context menu. When set to true, interaction with outside elements will be disabled and only menu content will be visible to screen readers.
    modal: Var[bool]

    _invalid_children: ClassVar[list[str]] = ["ContextMenuItem"]

    # Fired when the open state changes.
    on_open_change: EventHandler[passthrough_event_spec(bool)]

    # The reading direction of submenus when applicable. If omitted, inherits globally from DirectionProvider or assumes LTR (left-to-right) reading mode.
    dir: Var[LiteralDirType]


class ContextMenuTrigger(RadixThemesComponent):
    """Wraps the element that will open the context menu."""

    tag = "ContextMenu.Trigger"

    # Whether the trigger is disabled
    disabled: Var[bool]

    _valid_parents: ClassVar[list[str]] = ["ContextMenuRoot"]

    _invalid_children: ClassVar[list[str]] = ["ContextMenuContent"]

    _memoization_mode = MemoizationMode(recursive=False)


class ContextMenuContent(RadixThemesComponent):
    """The component that pops out when the context menu is open."""

    tag = "ContextMenu.Content"

    # Dropdown Menu Content size "1" - "2"
    size: Var[Responsive[LiteralSizeType]]

    # Variant of Dropdown Menu Content: "solid" | "soft"
    variant: Var[LiteralVariantType]

    # Override theme color for Dropdown Menu Content
    color_scheme: Var[LiteralAccentColor]

    # Renders the Dropdown Menu Content in higher contrast
    high_contrast: Var[bool]

    # Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False.
    as_child: Var[bool]

    # When True, keyboard navigation will loop from last item to first, and vice versa. Defaults to False.
    loop: Var[bool]

    # Used to force mounting when more control is needed. Useful when controlling animation with React animation libraries.
    force_mount: Var[bool]

    # The preferred side of the trigger to render against when open. Will be reversed when collisions occur and `avoid_collisions` is enabled.The position of the tooltip. Defaults to "top".
    side: Var[LiteralSideType]

    # The distance in pixels from the trigger. Defaults to 0.
    side_offset: Var[float | int]

    # The preferred alignment against the trigger. May change when collisions occur. Defaults to "center".
    align: Var[LiteralAlignType]

    # An offset in pixels from the "start" or "end" alignment options.
    align_offset: Var[float | int]

    # When true, overrides the side and align preferences to prevent collisions with boundary edges. Defaults to True.
    avoid_collisions: Var[bool]

    # The distance in pixels from the boundary edges where collision detection should occur. Accepts a number (same for all sides), or a partial padding object, for example: { "top": 20, "left": 20 }. Defaults to 0.
    collision_padding: Var[float | int | dict[str, float | int]]

    # The sticky behavior on the align axis. "partial" will keep the content in the boundary as long as the trigger is at least partially in the boundary whilst "always" will keep the content in the boundary regardless. Defaults to "partial".
    sticky: Var[LiteralStickyType]

    # Whether to hide the content when the trigger becomes fully occluded. Defaults to False.
    hide_when_detached: Var[bool]

    # Fired when focus moves back after closing.
    on_close_auto_focus: EventHandler[no_args_event_spec]

    # Fired when the escape key is pressed.
    on_escape_key_down: EventHandler[no_args_event_spec]

    # Fired when a pointer down event happens outside the context menu.
    on_pointer_down_outside: EventHandler[no_args_event_spec]

    # Fired when focus moves outside the context menu.
    on_focus_outside: EventHandler[no_args_event_spec]

    # Fired when the pointer interacts outside the context menu.
    on_interact_outside: EventHandler[no_args_event_spec]


class ContextMenuSub(RadixThemesComponent):
    """Contains all the parts of a submenu."""

    tag = "ContextMenu.Sub"

    # The controlled open state of the submenu. Must be used in conjunction with `on_open_change`.
    open: Var[bool]

    # The open state of the submenu when it is initially rendered. Use when you do not need to control its open state.
    default_open: Var[bool]

    # Fired when the open state changes.
    on_open_change: EventHandler[passthrough_event_spec(bool)]


class ContextMenuSubTrigger(RadixThemesComponent):
    """An item that opens a submenu."""

    tag = "ContextMenu.SubTrigger"

    # Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False.
    as_child: Var[bool]

    # Whether the trigger is disabled
    disabled: Var[bool]

    # Optional text used for typeahead purposes. By default the typeahead behavior will use the .textContent of the item. Use this when the content is complex, or you have non-textual content inside.
    text_value: Var[str]

    _valid_parents: ClassVar[list[str]] = ["ContextMenuContent", "ContextMenuSub"]

    _memoization_mode = MemoizationMode(recursive=False)


class ContextMenuSubContent(RadixThemesComponent):
    """The component that pops out when a submenu is open."""

    tag = "ContextMenu.SubContent"

    # Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False.
    as_child: Var[bool]

    # When True, keyboard navigation will loop from last item to first, and vice versa. Defaults to False.
    loop: Var[bool]

    # Used to force mounting when more control is needed. Useful when controlling animation with React animation libraries.
    force_mount: Var[bool]

    # The distance in pixels from the trigger. Defaults to 0.
    side_offset: Var[float | int]

    # An offset in pixels from the "start" or "end" alignment options.
    align_offset: Var[float | int]

    # When true, overrides the side and align preferences to prevent collisions with boundary edges. Defaults to True.
    avoid_collisions: Var[bool]

    # The distance in pixels from the boundary edges where collision detection should occur. Accepts a number (same for all sides), or a partial padding object, for example: { "top": 20, "left": 20 }. Defaults to 0.
    collision_padding: Var[float | int | dict[str, float | int]]

    # The sticky behavior on the align axis. "partial" will keep the content in the boundary as long as the trigger is at least partially in the boundary whilst "always" will keep the content in the boundary regardless. Defaults to "partial".
    sticky: Var[LiteralStickyType]

    # Whether to hide the content when the trigger becomes fully occluded. Defaults to False.
    hide_when_detached: Var[bool]

    _valid_parents: ClassVar[list[str]] = ["ContextMenuSub"]

    # Fired when the escape key is pressed.
    on_escape_key_down: EventHandler[no_args_event_spec]

    # Fired when a pointer down event happens outside the context menu.
    on_pointer_down_outside: EventHandler[no_args_event_spec]

    # Fired when focus moves outside the context menu.
    on_focus_outside: EventHandler[no_args_event_spec]

    # Fired when interacting outside the context menu.
    on_interact_outside: EventHandler[no_args_event_spec]


class ContextMenuItem(RadixThemesComponent):
    """The component that contains the context menu items."""

    tag = "ContextMenu.Item"

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # Shortcut to render a menu item as a link
    shortcut: Var[str]

    # Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False.
    as_child: Var[bool]

    # When true, prevents the user from interacting with the item.
    disabled: Var[bool]

    # Optional text used for typeahead purposes. By default the typeahead behavior will use the content of the item. Use this when the content is complex, or you have non-textual content inside.
    text_value: Var[str]

    _valid_parents: ClassVar[list[str]] = [
        "ContextMenuContent",
        "ContextMenuSubContent",
        "ContextMenuGroup",
    ]

    # Fired when the item is selected.
    on_select: EventHandler[no_args_event_spec]


class ContextMenuSeparator(RadixThemesComponent):
    """Separates items in a context menu."""

    tag = "ContextMenu.Separator"


class ContextMenuCheckbox(Checkbox):
    """The component that contains the checkbox."""

    tag = "ContextMenu.CheckboxItem"

    # Text to render as shortcut.
    shortcut: Var[str]


class ContextMenuLabel(RadixThemesComponent):
    """The component that contains the label."""

    tag = "ContextMenu.Label"

    # Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False.
    as_child: Var[bool]


class ContextMenuGroup(RadixThemesComponent):
    """The component that contains the group."""

    tag = "ContextMenu.Group"

    # Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False.
    as_child: Var[bool]

    _valid_parents: ClassVar[list[str]] = [
        "ContextMenuContent",
        "ContextMenuSubContent",
    ]


class ContextMenuRadioGroup(RadixThemesComponent):
    """The component that contains context menu radio items."""

    tag = "ContextMenu.RadioGroup"

    # Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False.
    as_child: Var[bool]

    # The value of the selected item in the group.
    value: Var[str]

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    # Fired when the value of the radio group changes.
    on_change: EventHandler[passthrough_event_spec(str)]

    _valid_parents: ClassVar[list[str]] = [
        "ContextMenuRadioItem",
        "ContextMenuSubContent",
        "ContextMenuContent",
        "ContextMenuSub",
    ]


class ContextMenuRadioItem(HighLevelRadioGroup):
    """The component that contains context menu radio items."""

    tag = "ContextMenu.RadioItem"

    # Override theme color for Dropdown Menu Content
    color_scheme: Var[LiteralAccentColor]

    # Change the default rendered element for the one passed as a child, merging their props and behavior. Defaults to False.
    as_child: Var[bool]

    # The unique value of the item.
    value: Var[str]

    # When true, prevents the user from interacting with the item.
    disabled: Var[bool]

    # Event handler called when the user selects an item (via mouse or keyboard). Calling event.preventDefault in this handler will prevent the context menu from closing when selecting that item.
    on_select: EventHandler[no_args_event_spec]

    # Optional text used for typeahead purposes. By default the typeahead behavior will use the .textContent of the item. Use this when the content is complex, or you have non-textual content inside.
    text_value: Var[str]


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
