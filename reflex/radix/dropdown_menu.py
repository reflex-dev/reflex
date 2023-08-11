"""The Radix dropdown menu component."""
from typing import Dict, Literal, Union

from reflex.components import Component
from reflex.vars import Var


class DropdownMenuComponent(Component):
    """Radix dropdown menu component."""

    library = "@radix-ui/react-dropdown-menu"
    is_default = False


class DropdownMenuRoot(DropdownMenuComponent):
    """Radix dropdown menu root. The onOpenChange prop is not currently supported."""

    tag = "Root"
    alias = "DropdownMenuRoot"

    default_open: Var[bool]
    open: Var[bool]
    modal: Var[bool]
    dir: Var[Literal["ltr", "rtl"]]


class DropdownMenuTrigger(DropdownMenuComponent):
    """Radix dropdown menu trigger."""

    tag = "Trigger"
    alias = "DropdownMenuTrigger"

    as_child: Var[bool]


class DropdownMenuPortal(DropdownMenuComponent):
    """Radix dropdown menu portal. The container prop is not currently supported."""

    tag = "Portal"
    alias = "DropdownMenuPortal"

    force_mount: Var[bool]


class DropdownMenuContent(DropdownMenuComponent):
    """Radix dropdown menu content. The event handler and collisionBoundary props are not currently supported."""

    tag = "Content"
    alias = "DropdownMenuContent"

    as_child: Var[bool]
    loop: Var[bool]
    force_mount: Var[bool]
    side: Var[Literal["top", "right", "bottom", "left"]]
    side_offset: Var[int]
    align: Var[Literal["start", "center", "end"]]
    align_offset: Var[int]
    avoid_collisions: Var[bool]
    collision_padding: Var[
        Union[int, Dict[Literal["top", "right", "bottom", "left"], int]]
    ]
    arrow_padding: Var[int]
    sticky: Var[Literal["partial", "always"]]
    hide_when_detached: Var[bool]


class DropdownMenuArrow(DropdownMenuComponent):
    """Radix dropdown menu arrow."""

    tag = "Arrow"
    alias = "DropdownMenuArrow"

    as_child: Var[bool]
    width: Var[int]
    height: Var[int]


class DropdownMenuItem(DropdownMenuComponent):
    """Radix dropdown menu item. The onSelect prop is not currently supported."""

    tag = "Item"
    alias = "DropdownMenuItem"

    as_child: Var[bool]
    disabled: Var[bool]
    text_value: Var[str]


class DropdownMenuGroup(DropdownMenuComponent):
    """Radix dropdown menu group."""

    tag = "Group"
    alias = "DropdownMenuGroup"

    as_child: Var[bool]


class DropdownMenuLabel(DropdownMenuComponent):
    """Radix dropdown menu label."""

    tag = "Label"
    alias = "DropdownMenuLabel"

    as_child: Var[bool]


class DropdownMenuCheckboxItem(DropdownMenuComponent):
    """Radix dropdown menu checkbox item. Event handler props are not currently supported."""

    tag = "CheckboxItem"
    alias = "DropdownMenuCheckboxItem"

    as_child: Var[bool]
    checked: Var[Union[bool, Literal["indeterminate"]]]
    disabled: Var[bool]
    text_value: Var[str]


class DropdownMenuRadioGroup(DropdownMenuComponent):
    """Radix dropdown menu radio group. The onValueChange prop is not currently supported."""

    tag = "RadioGroup"
    alias = "DropdownMenuRadioGroup"

    as_child: Var[bool]
    value: Var[str]


class DropdownMenuRadioItem(DropdownMenuComponent):
    """Radix dropdown menu radio item. The onSelect prop is not currently supported."""

    tag = "RadioItem"
    alias = "DropdownMenuRadioItem"

    as_child: Var[bool]
    value: Var[str]
    disabled: Var[bool]
    text_value: Var[str]


class DropdownMenuItemIndicator(DropdownMenuComponent):
    """Radix dropdown menu item indicator."""

    tag = "ItemIndicator"
    alias = "DropdownMenuItemIndicator"

    as_child: Var[bool]
    force_mount: Var[bool]


class DropdownMenuSeparator(DropdownMenuComponent):
    """Radix dropdown menu separator."""

    tag = "Separator"
    alias = "DropdownMenuSeparator"

    as_child: Var[bool]


class DropdownMenuSub(DropdownMenuComponent):
    """Radix dropdown menu sub. The onOpenChange prop is not currently supported."""

    tag = "Sub"
    alias = "DropdownMenuSub"

    default_open: Var[bool]
    open: Var[bool]


class DropdownMenuSubTrigger(DropdownMenuComponent):
    """Radix dropdown menu sub trigger."""

    tag = "SubTrigger"
    alias = "DropdownMenuSubTrigger"

    as_child: Var[bool]
    disabled: Var[bool]
    text_value: Var[str]


class DropdownMenuSubContent(DropdownMenuComponent):
    """Dropdown menu sub content. The event handler and collisionBoundary props are not currently supported."""

    tag = "SubContent"
    alias = "DropdownMenuSubContent"

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
