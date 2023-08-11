"""Radix toggle group components."""
from typing import List, Literal, Union

from reflex.components import Component
from reflex.vars import Var


class ToggleGroupComponent(Component):
    """Base class for all toggle group components."""

    library = "@radix-ui/react-toggle-group"
    is_default = False  # Use named exports.

    # Whether to use a child.
    as_child: Var[bool]


class ToggleGroupRoot(ToggleGroupComponent):
    """Radix toggle group root. The onValueChange prop is not currently supported and the orientation prop does not support the undefined value."""

    tag = "Root"
    alias = "ToggleGroupRoot"

    type_: Var[Literal["single", "multiple"]]
    value: Var[Union[str, List[str]]]
    default_value: Var[Union[str, List[str]]]
    disabled: Var[bool]
    roving_focus: Var[bool]
    orientation: Var[Literal["horizontal", "vertical"]]
    dir: Var[Literal["ltr", "rtl"]]
    loop: Var[bool]


class ToggleGroupItem(ToggleGroupComponent):
    """Radix toggle group item."""

    tag = "Item"
    alias = "ToggleGroupItem"

    value: Var[str]
    disabled: Var[bool]
