"""Radix tabs components."""
from typing import Literal, Optional

from reflex.components import Component


class TabsComponent(Component):
    """Base class for all tabs components."""

    library = "@radix-ui/react-tabs"

    is_default = False

    # Whether to use a child.
    as_child: Optional[bool]


class TabsRoot(TabsComponent):
    """Radix tabs root component. The onValueChange prop is not currently supported."""

    tag = "Root"
    alias = "TabsRoot"

    default_value: Optional[str]
    value: Optional[str]
    orientation: Optional[Literal["horizontal", "vertical"]]
    dir: Optional[Literal["ltr", "rtl"]]
    activation_mode: Optional[Literal["automatic", "manual"]]


class TabsList(TabsComponent):
    """Radix tabs list."""

    tag = "List"
    alias = "TabsList"

    loop: Optional[bool]


class TabsTrigger(TabsComponent):
    """Radix tabs trigger."""

    tag = "Trigger"
    alias = "TabsTrigger"

    value: str
    disabled: Optional[bool]


class TabsContent(TabsComponent):
    """Radix tabs content."""

    tag = "Content"
    alias = "TabsContent"

    value: str
    force_mount: Optional[bool]
