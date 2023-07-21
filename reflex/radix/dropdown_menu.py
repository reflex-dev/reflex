"""The Radix dropdown menu component."""
from typing import Dict, Literal, Optional, Union

from reflex.components import Component


class DropdownMenuComponent(Component):
    """Radix dropdown menu component."""

    library = "@radix-ui/react-dropdown-menu"
    is_default = False


class DropdownMenuRoot(DropdownMenuComponent):
    """Radix dropdown menu root. The onOpenChange prop is not currently supported."""

    tag = "Root"
    alias = "DropdownMenuRoot"

    default_open: Optional[bool]
    open: Optional[bool]
    modal: Optional[bool]
    dir: Optional[Literal["ltr", "rtl"]]


class DropdownMenuTrigger(DropdownMenuComponent):
    """Radix dropdown menu trigger."""

    tag = "Trigger"
    alias = "DropdownMenuTrigger"

    as_child: Optional[bool]


class DropdownMenuPortal(DropdownMenuComponent):
    """Radix dropdown menu portal. The container prop is not currently supported."""

    tag = "Portal"
    alias = "DropdownMenuPortal"

    force_mount: Optional[bool]


class DropdownMenuContent(DropdownMenuComponent):
    """Radix dropdown menu content. The event handler and collisionBoundary props are not currently supported."""

    tag = "Content"
    alias = "DropdownMenuContent"

    as_child: Optional[bool]
    loop: Optional[bool]
    force_mount: Optional[bool]
    side: Optional[Literal["top", "right", "bottom", "left"]]
    side_offset: Optional[int]
    align: Optional[Literal["start", "center", "end"]]
    align_offset: Optional[int]
    avoid_collisions: Optional[bool]
    collision_padding: Optional[
        Union[int, Dict[Literal["top", "right", "bottom", "left"], int]]
    ]
    arrow_padding: Optional[int]
    sticky: Optional[Literal["partial", "always"]]
    hide_when_detached: Optional[bool]


class DropdownMenuArrow(DropdownMenuComponent):
    """Radix dropdown menu arrow."""

    tag = "Arrow"
    alias = "DropdownMenuArrow"

    as_child: Optional[bool]
    width: Optional[int]
    height: Optional[int]


class DropdownMenuItem(DropdownMenuComponent):
    """Radix dropdown menu item. The onSelect prop is not currently supported."""

    tag = "Item"
    alias = "DropdownMenuItem"

    as_child: Optional[bool]
    disabled: Optional[bool]
    text_value: Optional[str]


class DropdownMenuGroup(DropdownMenuComponent):
    """Radix dropdown menu group."""

    tag = "Group"
    alias = "DropdownMenuGroup"

    as_child: Optional[bool]


class DropdownMenuLabel(DropdownMenuComponent):
    """Radix dropdown menu label."""

    tag = "Label"
    alias = "DropdownMenuLabel"

    as_child: Optional[bool]


class DropdownMenuCheckboxItem(DropdownMenuComponent):
    """Radix dropdown menu checkbox item. Event handler props are not currently supported."""

    tag = "CheckboxItem"
    alias = "DropdownMenuCheckboxItem"

    as_child: Optional[bool]
    checked: Optional[Union[bool, Literal["indeterminate"]]]
    disabled: Optional[bool]
    text_value: Optional[str]


class DropdownMenuRadioGroup(DropdownMenuComponent):
    """Radix dropdown menu radio group. The onValueChange prop is not currently supported."""

    tag = "RadioGroup"
    alias = "DropdownMenuRadioGroup"

    as_child: Optional[bool]
    value: Optional[str]


class DropdownMenuRadioItem(DropdownMenuComponent):
    """Radix dropdown menu radio item. The onSelect prop is not currently supported."""

    tag = "RadioItem"
    alias = "DropdownMenuRadioItem"

    as_child: Optional[bool]
    value: str
    disabled: Optional[bool]
    text_value: Optional[str]


class DropdownMenuItemIndicator(DropdownMenuComponent):
    """Radix dropdown menu item indicator."""

    tag = "ItemIndicator"
    alias = "DropdownMenuItemIndicator"

    as_child: Optional[bool]
    force_mount: Optional[bool]


class DropdownMenuSeparator(DropdownMenuComponent):
    """Radix dropdown menu separator."""

    tag = "Separator"
    alias = "DropdownMenuSeparator"

    as_child: Optional[bool]


class DropdownMenuSub(DropdownMenuComponent):
    """Radix dropdown menu sub. The onOpenChange prop is not currently supported."""

    tag = "Sub"
    alias = "DropdownMenuSub"

    default_open: Optional[bool]
    open: Optional[bool]


class DropdownMenuSubTrigger(DropdownMenuComponent):
    """Radix dropdown menu sub trigger."""

    tag = "SubTrigger"
    alias = "DropdownMenuSubTrigger"

    as_child: Optional[bool]
    disabled: Optional[bool]
    text_value: Optional[str]


class DropdownMenuSubContent(DropdownMenuComponent):
    """Dropdown menu sub content. The event handler and collisionBoundary props are not currently supported."""

    tag = "SubContent"
    alias = "DropdownMenuSubContent"

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
