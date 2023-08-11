"""The Radix context menu component."""
from typing import Dict, Literal, Union

from reflex.components import Component
from reflex.vars import Var


class ContextMenuComponent(Component):
    """Radix context menu component."""

    library = "@radix-ui/react-context-menu"
    is_default = False


class ContextMenuRoot(ContextMenuComponent):
    """Radix context menu root. The onOpenChange prop is not currently supported."""

    tag = "Root"
    alias = "ContextMenuRoot"

    dir: Var[Literal["ltr", "rtl"]]
    modal: Var[bool]


class ContextMenuTrigger(ContextMenuComponent):
    """Radix context menu trigger."""

    tag = "Trigger"
    alias = "ContextMenuTrigger"

    as_child: Var[bool]
    disabled: Var[bool]


class ContextMenuPortal(ContextMenuComponent):
    """Radix context menu portal. The container prop is not currently supported."""

    tag = "Portal"
    alias = "ContextMenuPortal"

    force_mount: Var[bool]


class ContextMenuContent(ContextMenuComponent):
    """Radix context menu content. The event handler and collisionBoundary props are not currently supported."""

    tag = "Content"
    alias = "ContextMenuContent"

    as_child: Var[bool]
    loop: Var[bool]
    force_mount: Var[bool]
    align_offset: Var[int]
    avoid_collisions: Var[bool]
    collision_padding: Var[
        Union[int, Dict[Literal["top", "right", "bottom", "left"], int]]
    ]
    arrow_padding: Var[int]
    sticky: Var[Literal["partial", "always"]]
    hide_when_detached: Var[bool]


class ContextMenuArrow(ContextMenuComponent):
    """Radix context menu arrow."""

    tag = "Arrow"
    alias = "ContextMenuArrow"

    as_child: Var[bool]
    width: Var[int]
    height: Var[int]


class ContextMenuItem(ContextMenuComponent):
    """Radix context menu item. The onSelect prop is not currently supported."""

    tag = "Item"
    alias = "ContextMenuItem"

    as_child: Var[bool]
    disabled: Var[bool]
    text_value: Var[str]


class ContextMenuGroup(ContextMenuComponent):
    """Radix context menu group."""

    tag = "Group"
    alias = "ContextMenuGroup"

    as_child: Var[bool]


class ContextMenuLabel(ContextMenuComponent):
    """Radix context menu label."""

    tag = "Label"
    alias = "ContextMenuLabel"

    as_child: Var[bool]


class ContextMenuCheckboxItem(ContextMenuComponent):
    """Radix context menu checkbox item. Event handler props are not currently supported."""

    tag = "CheckboxItem"
    alias = "ContextMenuCheckboxItem"

    as_child: Var[bool]
    checked: Var[Union[bool, Literal["indeterminate"]]]
    disabled: Var[bool]
    text_value: Var[str]


class ContextMenuRadioGroup(ContextMenuComponent):
    """Radix context menu radio group. The onValueChange prop is not currently supported."""

    tag = "RadioGroup"
    alias = "ContextMenuRadioGroup"

    as_child: Var[bool]
    value: Var[str]


class ContextMenuRadioItem(ContextMenuComponent):
    """Radix context menu radio item. The onSelect prop is not currently supported."""

    tag = "RadioItem"
    alias = "ContextMenuRadioItem"

    as_child: Var[bool]
    value: Var[str]
    disabled: Var[bool]
    text_value: Var[str]


class ContextMenuItemIndicator(ContextMenuComponent):
    """Radix context menu item indicator."""

    tag = "ItemIndicator"
    alias = "ContextMenuItemIndicator"

    as_child: Var[bool]
    force_mount: Var[bool]


class ContextMenuSeparator(ContextMenuComponent):
    """Radix context menu separator."""

    tag = "Separator"
    alias = "ContextMenuSeparator"

    as_child: Var[bool]


class ContextMenuSub(ContextMenuComponent):
    """Radix context menu sub. The onOpenChange prop is not currently supported."""

    tag = "Sub"
    alias = "ContextMenuSub"

    default_open: Var[bool]
    open: Var[bool]


class ContextMenuSubTrigger(ContextMenuComponent):
    """Radix context menu sub trigger."""

    tag = "SubTrigger"
    alias = "ContextMenuSubTrigger"

    as_child: Var[bool]
    disabled: Var[bool]
    text_value: Var[str]


class ContextMenuSubContent(ContextMenuComponent):
    """Dropdown menu sub content. The event handler and collisionBoundary props are not currently supported."""

    tag = "SubContent"
    alias = "ContextMenuSubContent"

    as_child: Var[bool]
    loop: Var[bool]
    force_mount: Var[bool]
    side_offset: Var[int]
    align_offset: Var[int]
    avoid_collisions: Var[bool]
    collision_padding: Var[
        Union[int, Dict[Literal["top", "right", "bottom", "left"], int]]
    ]
    arrow_padding: Var[int]
    sticky: Var[Literal["partial", "always"]]
    hide_when_detached: Var[bool]
