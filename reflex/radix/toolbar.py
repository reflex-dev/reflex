"""Radix toolbar component."""
from typing import List, Literal, Union

from reflex.components import Component
from reflex.vars import Var


class ToolbarComponent(Component):
    """Base class for all tooltip components."""

    library = "@radix-ui/react-toolbar"
    is_default = False


class ToolbarRoot(ToolbarComponent):
    """Radix toolbar root component. The orientation prop does not support the undefined value."""

    tag = "Root"
    alias = "ToolbarRoot"

    as_child: Var[bool]
    orientation: Var[Literal["horizontal", "vertical"]]
    dir: Var[Literal["ltr", "rtl"]]
    loop: Var[bool]


class ToolbarButton(ToolbarComponent):
    """Radix toolbar button."""

    tag = "Button"
    alias = "ToolbarButton"

    as_child: Var[bool]


class ToolbarLink(ToolbarComponent):
    """Radix toolbar link."""

    tag = "Link"
    alias = "ToolbarLink"

    as_child: Var[bool]


class ToolbarSeparator(ToolbarComponent):
    """Radix toolbar separator."""

    tag = "Separator"
    alias = "ToolbarSeparator"

    as_child: Var[bool]


class ToolbarToggleGroup(ToolbarComponent):
    """Radix toolbar toggle group component. The onValueChange prop is not currently supported."""

    tag = "ToggleGroup"
    alias = "ToolbarToggleGroup"

    as_child: Var[bool]
    type_: Var[Literal["single", "multiple"]]
    value: Var[Union[str, List[str]]]
    default_value: Var[Union[str, List[str]]]
    disabled: Var[bool]


class ToolbarToggleItem(ToolbarComponent):
    """Radix toolbar toggle item."""

    tag = "ToggleItem"
    alias = "ToolbarToggleItem"

    as_child: Var[bool]
    value: Var[str]
    disabled: Var[bool]
