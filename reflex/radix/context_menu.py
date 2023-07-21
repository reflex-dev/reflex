"""The Radix context menu component."""
from typing import Dict, Literal, Optional, Union

from reflex.components import Component


class ContextMenuComponent(Component):
    """Radix context menu component."""

    library = "@radix-ui/react-context-menu"
    is_default = False


class ContextMenuRoot(ContextMenuComponent):
    """Radix context menu root. The onOpenChange prop is not currently supported."""

    tag = "Root"
    alias = "ContextMenuRoot"

    dir: Optional[Literal["ltr", "rtl"]]
    modal: Optional[bool]


class ContextMenuTrigger(ContextMenuComponent):
    """Radix context menu trigger."""

    tag = "Trigger"
    alias = "ContextMenuTrigger"

    as_child: Optional[bool]
    disabled: Optional[bool]


class ContextMenuPortal(ContextMenuComponent):
    """Radix context menu portal. The container prop is not currently supported."""

    tag = "Portal"
    alias = "ContextMenuPortal"

    force_mount: Optional[bool]


class ContextMenuContent(ContextMenuComponent):
    """Radix context menu content. The event handler and collisionBoundary props are not currently supported."""

    tag = "Content"
    alias = "ContextMenuContent"

    as_child: Optional[bool]
    loop: Optional[bool]
    force_mount: Optional[bool]
    align_offset: Optional[int]
    avoid_collisions: Optional[bool]
    collision_padding: Optional[
        Union[int, Dict[Literal["top", "right", "bottom", "left"], int]]
    ]
    arrow_padding: Optional[int]
    sticky: Optional[Literal["partial", "always"]]
    hide_when_detached: Optional[bool]


class ContextMenuArrow(ContextMenuComponent):
    """Radix context menu arrow."""

    tag = "Arrow"
    alias = "ContextMenuArrow"

    as_child: Optional[bool]
    width: Optional[int]
    height: Optional[int]


class ContextMenuItem(ContextMenuComponent):
    """Radix context menu item. The onSelect prop is not currently supported."""

    tag = "Item"
    alias = "ContextMenuItem"

    as_child: Optional[bool]
    disabled: Optional[bool]
    text_value: Optional[str]


class ContextMenuGroup(ContextMenuComponent):
    """Radix context menu group."""

    tag = "Group"
    alias = "ContextMenuGroup"

    as_child: Optional[bool]


class ContextMenuLabel(ContextMenuComponent):
    """Radix context menu label."""

    tag = "Label"
    alias = "ContextMenuLabel"

    as_child: Optional[bool]


class ContextMenuCheckboxItem(ContextMenuComponent):
    """Radix context menu checkbox item. Event handler props are not currently supported."""

    tag = "CheckboxItem"
    alias = "ContextMenuCheckboxItem"

    as_child: Optional[bool]
    checked: Optional[Union[bool, Literal["indeterminate"]]]
    disabled: Optional[bool]
    text_value: Optional[str]


class ContextMenuRadioGroup(ContextMenuComponent):
    """Radix context menu radio group. The onValueChange prop is not currently supported."""

    tag = "RadioGroup"
    alias = "ContextMenuRadioGroup"

    as_child: Optional[bool]
    value: Optional[str]


class ContextMenuRadioItem(ContextMenuComponent):
    """Radix context menu radio item. The onSelect prop is not currently supported."""

    tag = "RadioItem"
    alias = "ContextMenuRadioItem"

    as_child: Optional[bool]
    value: str
    disabled: Optional[bool]
    text_value: Optional[str]


class ContextMenuItemIndicator(ContextMenuComponent):
    """Radix context menu item indicator."""

    tag = "ItemIndicator"
    alias = "ContextMenuItemIndicator"

    as_child: Optional[bool]
    force_mount: Optional[bool]


class ContextMenuSeparator(ContextMenuComponent):
    """Radix context menu separator."""

    tag = "Separator"
    alias = "ContextMenuSeparator"

    as_child: Optional[bool]


class ContextMenuSub(ContextMenuComponent):
    """Radix context menu sub. The onOpenChange prop is not currently supported."""

    tag = "Sub"
    alias = "ContextMenuSub"

    default_open: Optional[bool]
    open: Optional[bool]


class ContextMenuSubTrigger(ContextMenuComponent):
    """Radix context menu sub trigger."""

    tag = "SubTrigger"
    alias = "ContextMenuSubTrigger"

    as_child: Optional[bool]
    disabled: Optional[bool]
    text_value: Optional[str]


class ContextMenuSubContent(ContextMenuComponent):
    """Dropdown menu sub content. The event handler and collisionBoundary props are not currently supported."""

    tag = "SubContent"
    alias = "ContextMenuSubContent"

    as_child: Optional[bool]
    loop: Optional[bool]
    force_mount: Optional[bool]
    side_offset: Optional[int]
    align_offset: Optional[int]
    avoid_collisions: Optional[bool]
    collision_padding: Optional[
        Union[int, Dict[Literal["top", "right", "bottom", "left"], int]]
    ]
    arrow_padding: Optional[int]
    sticky: Optional[Literal["partial", "always"]]
    hide_when_detached: Optional[bool]
