"""Radix tabs components."""
from typing import Literal

from reflex.components import Component
from reflex.vars import Var


class TabsComponent(Component):
    """Base class for all tabs components."""

    library = "@radix-ui/react-tabs"

    is_default = False

    # Whether to use a child.
    as_child: Var[bool]


class TabsRoot(TabsComponent):
    """Radix tabs root component. The onValueChange prop is not currently supported."""

    tag = "Root"
    alias = "TabsRoot"

    default_value: Var[str]
    value: Var[str]
    orientation: Var[Literal["horizontal", "vertical"]]
    dir: Var[Literal["ltr", "rtl"]]
    activation_mode: Var[Literal["automatic", "manual"]]


class TabsList(TabsComponent):
    """Radix tabs list."""

    tag = "List"
    alias = "TabsList"

    loop: Var[bool]


class TabsTrigger(TabsComponent):
    """Radix tabs trigger."""

    tag = "Trigger"
    alias = "TabsTrigger"

    value: str
    disabled: Var[bool]


class TabsContent(TabsComponent):
    """Radix tabs content."""

    tag = "Content"
    alias = "TabsContent"

    value: str
    force_mount: Var[bool]
