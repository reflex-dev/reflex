"""Radix toggle group components."""
from typing import List, Literal, Optional, Union

from reflex.components import Component


class ToggleGroupComponent(Component):
    """Base class for all toggle group components."""

    library = "@radix-ui/react-toggle-group"

    is_default = False  # Use named exports.

    # Whether to use a child.
    as_child: Optional[bool]


class ToggleGroupRoot(ToggleGroupComponent):
    """Radix toggle group root. The onValueChange prop is not currently supported and the orientation prop does not support the undefined value."""

    tag = "Root"
    alias = "ToggleGroupRoot"

    type: Literal["single", "multiple"]
    value: Optional[Union[str, List[str]]]
    default_value: Optional[Union[str, List[str]]]
    disabled: Optional[bool]
    roving_focus: Optional[bool]
    orientation: Optional[Literal["horizontal", "vertical"]]
    dir: Optional[Literal["ltr", "rtl"]]
    loop: Optional[bool]


class ToggleGroupItem(ToggleGroupComponent):
    """Radix toggle group item."""

    tag = "Item"
    alias = "ToggleGroupItem"

    value: str
    disabled: Optional[bool]
