"""The Radix menubar component."""
from typing import Dict, Literal, Optional, Union

from reflex.components import Component


class MenubarComponent(Component):
    """Radix menubar component."""

    library = "@radix-ui/react-menubar"
    is_default = False


class MenubarRoot(MenubarComponent):
    """Radix menubar root. The onValueChange prop is not currently supported."""

    tag = "Root"
    alias = "MenubarRoot"

    as_child: Optional[bool]
    default_value: Optional[str]
    value: Optional[str]
    dir: Optional[Literal["ltr", "rtl"]]
    loop: Optional[bool]


class MenubarMenu(MenubarComponent):
    """Radix menubar menu."""

    tag = "Menu"
    alias = "MenubarMenu"

    as_child: Optional[bool]
    value: Optional[str]


class MenubarTrigger(MenubarComponent):
    """Radix menubar item."""

    tag = "Trigger"
    alias = "MenubarTrigger"

    as_child: Optional[bool]


class MenubarPortal(MenubarComponent):
    """Radix menubar portal. The container prop is not currently supported."""

    tag = "Portal"
    alias = "MenubarPortal"

    force_mount: Optional[bool]


class MenubarContent(MenubarComponent):
    """Radix menubar content. The event handler and collisionBoundary props are not currently supported."""

    tag = "Content"
    alias = "MenubarContent"

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


class MenubarArrow(MenubarComponent):
    """Radix menubar arrow."""

    tag = "Arrow"
    alias = "MenubarArrow"

    as_child: Optional[bool]
    width: Optional[int]
    height: Optional[int]


class MenubarItem(MenubarComponent):
    """Radix menubar item. The onSelect prop is not currently supported."""

    tag = "Item"
    alias = "MenubarItem"

    as_child: Optional[bool]
    disabled: Optional[bool]
    text_value: Optional[str]


class MenubarGroup(MenubarComponent):
    """Radix menubar group."""

    tag = "Group"
    alias = "MenubarGroup"

    as_child: Optional[bool]


class MenubarLabel(MenubarComponent):
    """Radix menubar label."""

    tag = "Label"
    alias = "MenubarLabel"

    as_child: Optional[bool]


class MenubarCheckboxItem(MenubarComponent):
    """Radix menubar checkbox item. Event handler props are not currently supported."""

    tag = "CheckboxItem"
    alias = "MenubarCheckboxItem"

    as_child: Optional[bool]
    checked: Optional[Union[bool, Literal["indeterminate"]]]
    disabled: Optional[bool]
    text_value: Optional[str]


class MenubarRadioGroup(MenubarComponent):
    """Radix menubar radio group. The onValueChange prop is not currently supported."""

    tag = "RadioGroup"
    alias = "MenubarRadioGroup"

    as_child: Optional[bool]
    value: Optional[str]


class MenubarRadioItem(MenubarComponent):
    """Radix menubar radio item. The onSelect prop is not currently supported."""

    tag = "RadioItem"
    alias = "MenubarRadioItem"

    as_child: Optional[bool]
    value: str
    disabled: Optional[bool]
    text_value: Optional[str]


class MenubarItemIndicator(MenubarComponent):
    """Radix menubar item indicator."""

    tag = "ItemIndicator"
    alias = "MenubarItemIndicator"

    as_child: Optional[bool]
    force_mount: Optional[bool]


class MenubarSeparator(MenubarComponent):
    """Radix menubar separator."""

    tag = "Separator"
    alias = "MenubarSeparator"

    as_child: Optional[bool]


class MenubarSub(MenubarComponent):
    """Radix menubar sub. The onOpenChange prop is not currently supported."""

    tag = "Sub"
    alias = "MenubarSub"

    default_open: Optional[bool]
    open: Optional[bool]


class MenubarSubTrigger(MenubarComponent):
    """Radix menubar sub trigger."""

    tag = "SubTrigger"
    alias = "MenubarSubTrigger"

    as_child: Optional[bool]
    disabled: Optional[bool]
    text_value: Optional[str]


class MenubarSubContent(MenubarComponent):
    """Radix menubar sub content. The event handler and collisionBoundary props are not currently supported."""

    tag = "SubContent"
    alias = "MenubarSubContent"

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
