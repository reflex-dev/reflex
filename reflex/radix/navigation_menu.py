"""A Radix navigation menu component."""
from typing import Literal

from reflex.components import Component
from reflex.vars import Var


class NavigationMenuComponent(Component):
    """Base class for all navigation menu components."""

    library = "@radix-ui/react-navigation-menu"
    is_default = False


class NavigationMenuRoot(NavigationMenuComponent):
    """The root container for a navigation menu. The onValueChange prop is not currently supported."""

    tag = "Root"
    alias = "NavigationMenuRoot"

    default_value: Var[str]
    value: Var[str]
    delay_duration: Var[int]
    skip_delay_duration: Var[int]
    dir: Var[Literal["ltr", "rtl"]]
    orientation: Var[Literal["horizontal", "vertical"]]


class NavigationMenuSub(NavigationMenuComponent):
    """Signifies a submenu. The onValueChange prop is not currently supported."""

    tag = "Sub"
    alias = "NavigationMenuSub"

    default_value: Var[str]
    value: Var[str]
    orientation: Var[Literal["horizontal", "vertical"]]


class NavigationMenuList(NavigationMenuComponent):
    """Contains the top level menu items."""

    tag = "List"
    alias = "NavigationMenuList"

    as_child: Var[bool]


class NavigationMenuItem(NavigationMenuComponent):
    """A top level menu item."""

    tag = "Item"
    alias = "NavigationMenuItem"

    as_child: Var[bool]
    value: Var[str]


class NavigationMenuTrigger(NavigationMenuComponent):
    """The button that toggles the content."""

    tag = "Trigger"
    alias = "NavigationMenuTrigger"

    as_child: Var[bool]


class NavigationMenuContent(NavigationMenuComponent):
    """Contains the content associated with each trigger. Event handler props are not currently supported."""

    tag = "Content"
    alias = "NavigationMenuContent"

    as_child: Var[bool]
    disable_outside_pointer_events: Var[bool]
    force_mount: Var[bool]


class NavigationMenuLink(NavigationMenuComponent):
    """A navigational link. The onSelect prop is not currently supported."""

    tag = "Link"
    alias = "NavigationMenuLink"

    as_child: Var[bool]
    active: Var[bool]


class NavigationMenuIndicator(NavigationMenuComponent):
    """An optional indicator to highlight the active trigger."""

    tag = "Indicator"
    alias = "NavigationMenuIndicator"

    as_child: Var[bool]
    force_mount: Var[bool]


class NavigationMenuViewport(NavigationMenuComponent):
    """Renders active content outside the menu."""

    tag = "Viewport"
    alias = "NavigationMenuViewport"

    as_child: Var[bool]
    force_mount: Var[bool]
