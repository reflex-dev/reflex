"""Radix toolbar component."""
from typing import List, Literal, Optional, Union

from reflex.components import Component


class ToolbarComponent(Component):
    """Base class for all tooltip components."""

    library = "@radix-ui/react-toolbar"

    is_default = False


class ToolbarRoot(ToolbarComponent):
    """Radix toolbar root component. The orientation prop does not support the undefined value."""

    tag = "Root"
    alias = "ToolbarRoot"

    as_child: Optional[bool]
    orientation: Optional[Literal["horizontal", "vertical"]]
    dir: Optional[Literal["ltr", "rtl"]]
    loop: Optional[bool]


class ToolbarButton(ToolbarComponent):
    """Radix toolbar button."""

    tag = "Button"
    alias = "ToolbarButton"

    as_child: Optional[bool]


class ToolbarLink(ToolbarComponent):
    """Radix toolbar link."""

    tag = "Link"
    alias = "ToolbarLink"

    as_child: Optional[bool]


class ToolbarSeparator(ToolbarComponent):
    """Radix toolbar separator."""

    tag = "Separator"
    alias = "ToolbarSeparator"

    as_child: Optional[bool]


class ToolbarToggleGroup(ToolbarComponent):
    """Radix toolbar toggle group component. The onValueChange prop is not currently supported."""

    tag = "ToggleGroup"
    alias = "ToolbarToggleGroup"

    as_child: Optional[bool]
    type: Literal["single", "multiple"]
    value: Optional[Union[str, List[str]]]
    default_value: Optional[Union[str, List[str]]]
    disabled: Optional[bool]


class ToolbarToggleItem(ToolbarComponent):
    """Radix toolbar toggle item."""

    tag = "ToggleItem"
    alias = "ToolbarToggleItem"

    as_child: Optional[bool]
    value: str
    disabled: Optional[bool]
