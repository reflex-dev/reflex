"""Radix radio group components."""
from typing import List, Literal, Union

from reflex.components import Component
from reflex.vars import Var


class RadioGroupComponent(Component):
    """Base class for all radio group components."""

    library = "@radix-ui/react-radio-group"

    is_default = False  # Use named exports.

    # Whether to use a child.
    as_child: Var[bool]


class RadioGroupRoot(RadioGroupComponent):
    """Radix radio group root. The onValueChange prop is not currently supported and the orientation prop does not support the undefined value."""

    tag = "Root"
    alias = "RadioGroupRoot"

    default_value: Var[Union[str, List[str]]]
    value: Var[Union[str, List[str]]]
    disabled: Var[bool]
    name: Var[str]
    required: Var[bool]
    orientation: Var[Literal["horizontal", "vertical"]]
    dir: Var[Literal["ltr", "rtl"]]
    loop: Var[bool]


class RadioGroupItem(RadioGroupComponent):
    """Radix radio group item."""

    tag = "Item"
    alias = "RadioGroupItem"

    value: Var[str]
    disabled: Var[bool]
    required: Var[bool]


class RadioGroupIndicator(RadioGroupComponent):
    """Radix radio group indicator."""

    tag = "Indicator"
    alias = "RadioGroupIndicator"

    force_mount: Var[bool]
