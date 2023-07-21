"""Radix radio group components."""
from typing import List, Literal, Optional, Union

from reflex.components import Component


class RadioGroupComponent(Component):
    """Base class for all radio group components."""

    library = "@radix-ui/react-radio-group"

    is_default = False  # Use named exports.

    # Whether to use a child.
    as_child: Optional[bool]


class RadioGroupRoot(RadioGroupComponent):
    """Radix radio group root. The onValueChange prop is not currently supported and the orientation prop does not support the undefined value."""

    tag = "Root"
    alias = "RadioGroupRoot"

    default_value: Optional[Union[str, List[str]]]
    value: Optional[Union[str, List[str]]]
    disabled: Optional[bool]
    name: Optional[str]
    required: Optional[bool]
    orientation: Optional[Literal["horizontal", "vertical"]]
    dir: Optional[Literal["ltr", "rtl"]]
    loop: Optional[bool]


class RadioGroupItem(RadioGroupComponent):
    """Radix radio group item."""

    tag = "Item"
    alias = "RadioGroupItem"

    value: Optional[str]
    disabled: Optional[bool]
    required: Optional[bool]


class RadioGroupIndicator(RadioGroupComponent):
    """Radix radio group indicator."""

    tag = "Indicator"
    alias = "RadioGroupIndicator"

    force_mount: Optional[bool]
