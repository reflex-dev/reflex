"""Radix select components."""
from typing import Dict, Literal, Optional, Union

from reflex.components import Component


class SelectComponent(Component):
    """Base class for all select components."""

    library = "@radix-ui/react-select"

    is_default = False


class SelectRoot(SelectComponent):
    """Radix select root component. The onValueChange prop is not currently supported."""

    tag = "Root"
    alias = "SelectRoot"

    default_value: Optional[str]
    value: Optional[str]
    default_open: Optional[bool]
    open: Optional[bool]
    dir: Optional[str]
    name: Optional[str]
    disabled: Optional[bool]
    required: Optional[bool]


class SelectTrigger(SelectComponent):
    """Radix select trigger."""

    tag = "Trigger"
    alias = "SelectTrigger"

    as_child: Optional[bool]


class SelectValue(SelectComponent):
    """Radix select value component. The placeholder prop only supports strings, not React children."""

    tag = "Value"
    alias = "SelectValue"

    as_child: Optional[bool]
    placeholder: Optional[str]


class SelectIcon(Component):
    """Radix select icon."""

    tag = "Icon"
    alias = "SelectIcon"

    as_child: Optional[bool]


class SelectPortal(SelectComponent):
    """Radix select portal component. The container prop is not currently supported."""

    tag = "Portal"
    alias = "SelectPortal"

    container: Optional[bool]


class SelectContent(SelectComponent):
    """Radix select content. The event handler and collisionBoundary props are not currently supported."""

    tag = "Content"
    alias = "SelectContent"

    as_child: Optional[bool]
    position: Optional[Literal["item-aligned", "popper"]]
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


class SelectViewport(SelectComponent):
    """Radix select viewport."""

    tag = "Viewport"
    alias = "SelectViewport"

    as_child: Optional[bool]


class SelectItem(SelectComponent):
    """Radix select item."""

    tag = "Item"
    alias = "SelectItem"

    as_child: Optional[bool]
    value: str
    disabled: Optional[bool]
    text_value: Optional[str]


class SelectItemText(SelectComponent):
    """Radix select item text."""

    tag = "ItemText"
    alias = "SelectItemText"

    as_child: Optional[bool]


class SelectItemIndicator(SelectComponent):
    """Radix select item indicator."""

    tag = "ItemIndicator"
    alias = "SelectItemIndicator"

    as_child: Optional[bool]


class SelectScrollUpButton(SelectComponent):
    """Radix select scroll up button."""

    tag = "ScrollUpButton"
    alias = "SelectScrollUpButton"

    as_child: Optional[bool]


class SelectScrollDownButton(SelectComponent):
    """Radix select scroll down button."""

    tag = "ScrollDownButton"
    alias = "SelectScrollDownButton"

    as_child: Optional[bool]


class SelectGroup(SelectComponent):
    """Radix select group."""

    tag = "Group"
    alias = "SelectGroup"

    as_child: Optional[bool]


class SelectLabel(SelectComponent):
    """Radix select label."""

    tag = "Label"
    alias = "SelectLabel"

    as_child: Optional[bool]


class SelectSeparator(SelectComponent):
    """Radix select separator."""

    tag = "Separator"
    alias = "SelectSeparator"

    as_child: Optional[bool]


class SelectArrow(SelectComponent):
    """Radix select arrow."""

    tag = "Arrow"
    alias = "SelectArrow"

    as_child: Optional[bool]
    width: Optional[int]
    height: Optional[int]
