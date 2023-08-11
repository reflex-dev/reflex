"""The Radix menubar component."""
from typing import Dict, Literal, Union

from reflex.components import Component
from reflex.vars import Var


class MenubarComponent(Component):
    """Radix menubar component."""

    library = "@radix-ui/react-menubar"
    is_default = False


class MenubarRoot(MenubarComponent):
    """Radix menubar root. The onValueChange prop is not currently supported."""

    tag = "Root"
    alias = "MenubarRoot"

    as_child: Var[bool]
    default_value: Var[str]
    value: Var[str]
    dir: Var[Literal["ltr", "rtl"]]
    loop: Var[bool]


class MenubarMenu(MenubarComponent):
    """Radix menubar menu."""

    tag = "Menu"
    alias = "MenubarMenu"

    as_child: Var[bool]
    value: Var[str]


class MenubarTrigger(MenubarComponent):
    """Radix menubar item."""

    tag = "Trigger"
    alias = "MenubarTrigger"

    as_child: Var[bool]


class MenubarPortal(MenubarComponent):
    """Radix menubar portal. The container prop is not currently supported."""

    tag = "Portal"
    alias = "MenubarPortal"

    force_mount: Var[bool]


class MenubarContent(MenubarComponent):
    """Radix menubar content. The event handler and collisionBoundary props are not currently supported."""

    tag = "Content"
    alias = "MenubarContent"

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


class MenubarArrow(MenubarComponent):
    """Radix menubar arrow."""

    tag = "Arrow"
    alias = "MenubarArrow"

    as_child: Var[bool]
    width: Var[int]
    height: Var[int]


class MenubarItem(MenubarComponent):
    """Radix menubar item. The onSelect prop is not currently supported."""

    tag = "Item"
    alias = "MenubarItem"

    as_child: Var[bool]
    disabled: Var[bool]
    text_value: Var[str]


class MenubarGroup(MenubarComponent):
    """Radix menubar group."""

    tag = "Group"
    alias = "MenubarGroup"

    as_child: Var[bool]


class MenubarLabel(MenubarComponent):
    """Radix menubar label."""

    tag = "Label"
    alias = "MenubarLabel"

    as_child: Var[bool]


class MenubarCheckboxItem(MenubarComponent):
    """Radix menubar checkbox item. Event handler props are not currently supported."""

    tag = "CheckboxItem"
    alias = "MenubarCheckboxItem"

    as_child: Var[bool]
    checked: Var[Union[bool, Literal["indeterminate"]]]
    disabled: Var[bool]
    text_value: Var[str]


class MenubarRadioGroup(MenubarComponent):
    """Radix menubar radio group. The onValueChange prop is not currently supported."""

    tag = "RadioGroup"
    alias = "MenubarRadioGroup"

    as_child: Var[bool]
    value: Var[str]


class MenubarRadioItem(MenubarComponent):
    """Radix menubar radio item. The onSelect prop is not currently supported."""

    tag = "RadioItem"
    alias = "MenubarRadioItem"

    as_child: Var[bool]
    value: Var[str]
    disabled: Var[bool]
    text_value: Var[str]


class MenubarItemIndicator(MenubarComponent):
    """Radix menubar item indicator."""

    tag = "ItemIndicator"
    alias = "MenubarItemIndicator"

    as_child: Var[bool]
    force_mount: Var[bool]


class MenubarSeparator(MenubarComponent):
    """Radix menubar separator."""

    tag = "Separator"
    alias = "MenubarSeparator"

    as_child: Var[bool]


class MenubarSub(MenubarComponent):
    """Radix menubar sub. The onOpenChange prop is not currently supported."""

    tag = "Sub"
    alias = "MenubarSub"

    default_open: Var[bool]
    open: Var[bool]


class MenubarSubTrigger(MenubarComponent):
    """Radix menubar sub trigger."""

    tag = "SubTrigger"
    alias = "MenubarSubTrigger"

    as_child: Var[bool]
    disabled: Var[bool]
    text_value: Var[str]


class MenubarSubContent(MenubarComponent):
    """Radix menubar sub content. The event handler and collisionBoundary props are not currently supported."""

    tag = "SubContent"
    alias = "MenubarSubContent"

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
