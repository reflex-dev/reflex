"""Radix select components."""
from typing import Dict, Literal, Union

from reflex.components import Component
from reflex.vars import Var


class SelectComponent(Component):
    """Base class for all select components."""

    library = "@radix-ui/react-select"

    is_default = False


class SelectRoot(SelectComponent):
    """Radix select root component. The onValueChange prop is not currently supported."""

    tag = "Root"
    alias = "SelectRoot"

    default_value: Var[str]
    value: Var[str]
    default_open: Var[bool]
    open: Var[bool]
    dir: Var[str]
    name: Var[str]
    disabled: Var[bool]
    required: Var[bool]


class SelectTrigger(SelectComponent):
    """Radix select trigger."""

    tag = "Trigger"
    alias = "SelectTrigger"

    as_child: Var[bool]


class SelectValue(SelectComponent):
    """Radix select value component. The placeholder prop only supports strings, not React children."""

    tag = "Value"
    alias = "SelectValue"

    as_child: Var[bool]
    placeholder: Var[str]


class SelectIcon(Component):
    """Radix select icon."""

    tag = "Icon"
    alias = "SelectIcon"

    as_child: Var[bool]


class SelectPortal(SelectComponent):
    """Radix select portal component. The container prop is not currently supported."""

    tag = "Portal"
    alias = "SelectPortal"

    container: Var[bool]


class SelectContent(SelectComponent):
    """Radix select content. The event handler and collisionBoundary props are not currently supported."""

    tag = "Content"
    alias = "SelectContent"

    as_child: Var[bool]
    position: Var[Literal["item-aligned", "popper"]]
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


class SelectViewport(SelectComponent):
    """Radix select viewport."""

    tag = "Viewport"
    alias = "SelectViewport"

    as_child: Var[bool]


class SelectItem(SelectComponent):
    """Radix select item."""

    tag = "Item"
    alias = "SelectItem"

    as_child: Var[bool]
    value: Var[str]
    disabled: Var[bool]
    text_value: Var[str]


class SelectItemText(SelectComponent):
    """Radix select item text."""

    tag = "ItemText"
    alias = "SelectItemText"

    as_child: Var[bool]


class SelectItemIndicator(SelectComponent):
    """Radix select item indicator."""

    tag = "ItemIndicator"
    alias = "SelectItemIndicator"

    as_child: Var[bool]


class SelectScrollUpButton(SelectComponent):
    """Radix select scroll up button."""

    tag = "ScrollUpButton"
    alias = "SelectScrollUpButton"

    as_child: Var[bool]


class SelectScrollDownButton(SelectComponent):
    """Radix select scroll down button."""

    tag = "ScrollDownButton"
    alias = "SelectScrollDownButton"

    as_child: Var[bool]


class SelectGroup(SelectComponent):
    """Radix select group."""

    tag = "Group"
    alias = "SelectGroup"

    as_child: Var[bool]


class SelectLabel(SelectComponent):
    """Radix select label."""

    tag = "Label"
    alias = "SelectLabel"

    as_child: Var[bool]


class SelectSeparator(SelectComponent):
    """Radix select separator."""

    tag = "Separator"
    alias = "SelectSeparator"

    as_child: Var[bool]


class SelectArrow(SelectComponent):
    """Radix select arrow."""

    tag = "Arrow"
    alias = "SelectArrow"

    as_child: Var[bool]
    width: Var[int]
    height: Var[int]
