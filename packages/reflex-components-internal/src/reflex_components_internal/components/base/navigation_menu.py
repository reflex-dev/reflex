"""Custom navigation menu component."""

from typing import Literal

from reflex.components.component import Component, ComponentNamespace
from reflex.event import EventHandler, passthrough_event_spec
from reflex.utils.imports import ImportVar
from reflex.vars.base import Var
from reflex_components_internal.components.base_ui import PACKAGE_NAME, BaseUIComponent

LiteralNavigationMenuOrientation = Literal["horizontal", "vertical"]
LiteralSide = Literal["top", "right", "bottom", "left"]
LiteralAlign = Literal["start", "center", "end"]
LiteralPositionMethod = Literal["absolute", "fixed"]
LiteralCollisionAvoidance = Literal["flip", "shift", "auto"]


class ClassNames:
    """Class names for navigation menu components."""

    ROOT = "min-w-max rounded-lg bg-secondary-1 p-1 text-secondary-12"
    LIST = "relative flex"
    ITEM = "relative"
    TRIGGER = "box-border flex items-center justify-center gap-1.5 h-10 px-2 xs:px-3.5 m-0 rounded-ui-md bg-secondary-1 text-secondary-12 font-medium text-[0.925rem] xs:text-base leading-6 select-none no-underline hover:bg-secondary-3 active:bg-secondary-3 data-[popup-open]:bg-secondary-3 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary-4"
    CONTENT = "w-max max-w-[calc(100vw-40px)] sm:max-w-[600px] p-6 transition-[opacity,transform,translate] duration-[0.35s] ease-[cubic-bezier(0.22,1,0.36,1)] data-[starting-style]:opacity-0 data-[ending-style]:opacity-0 data-[starting-style]:data-[activation-direction=left]:translate-x-[-50%] data-[starting-style]:data-[activation-direction=right]:translate-x-[50%] data-[ending-style]:data-[activation-direction=left]:translate-x-[50%] data-[ending-style]:data-[activation-direction=right]:translate-x-[-50%]"
    LINK = "block rounded-ui-md p-2 xs:p-3 no-underline text-inherit hover:bg-secondary-3 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary-4"
    ICON = "transition-transform duration-200 ease-in-out data-[popup-open]:rotate-180 text-secondary-10"
    PORTAL = ""
    POSITIONER = "box-border h-[var(--positioner-height)] w-[var(--positioner-width)] max-w-[var(--available-width)] transition-[top,left,right,bottom] duration-[0.35s] ease-[cubic-bezier(0.22,1,0.36,1)] before:absolute before:content-[''] data-[instant]:transition-none data-[side=bottom]:before:top-[-10px] data-[side=bottom]:before:right-0 data-[side=bottom]:before:left-0 data-[side=bottom]:before:h-2.5 data-[side=left]:before:top-0 data-[side=left]:before:right-[-10px] data-[side=left]:before:bottom-0 data-[side=left]:before:w-2.5 data-[side=right]:before:top-0 data-[side=right]:before:bottom-0 data-[side=right]:before:left-[-10px] data-[side=right]:before:w-2.5 data-[side=top]:before:right-0 data-[side=top]:before:bottom-[-10px] data-[side=top]:before:left-0 data-[side=top]:before:h-2.5"
    POPUP = "relative h-[var(--popup-height)] w-max origin-[var(--transform-origin)] rounded-lg bg-secondary-1 text-secondary-12 shadow-large border border-secondary-a4 transition-[opacity,transform,width,height,scale,translate] duration-[0.35s] ease-[cubic-bezier(0.22,1,0.36,1)] data-[ending-style]:scale-90 data-[ending-style]:opacity-0 data-[ending-style]:duration-150 data-[starting-style]:scale-90 data-[starting-style]:opacity-0 min-[500px]:w-[var(--popup-width)] xs:w-[var(--popup-width)]"
    VIEWPORT = "relative h-full w-full overflow-hidden"
    ARROW = "flex transition-[left] duration-[0.35s] ease-[cubic-bezier(0.22,1,0.36,1)] data-[side=bottom]:top-[-8px] data-[side=left]:right-[-13px] data-[side=left]:rotate-90 data-[side=right]:left-[-13px] data-[side=right]:-rotate-90 data-[side=top]:bottom-[-8px] data-[side=top]:rotate-180"
    BACKDROP = "fixed inset-0 z-40"


class NavigationMenuBaseComponent(BaseUIComponent):
    """Base component for navigation menu components."""

    library = f"{PACKAGE_NAME}/navigation-menu"

    @property
    def import_var(self):
        """Return the import variable for the navigation menu component."""
        return ImportVar(tag="NavigationMenu", package_path="", install=False)


class NavigationMenuRoot(NavigationMenuBaseComponent):
    """Groups all parts of the navigation menu. Renders a <nav> element at the root, or <div> element when nested."""

    tag = "NavigationMenu.Root"

    # The controlled value of the navigation menu item that should be currently open. When non-nullish, the menu will be open. When nullish, the menu will be closed. To render an uncontrolled navigation menu, use the defaultValue prop instead.
    value: Var[str]

    # The uncontrolled value of the item that should be initially selected. To render a controlled navigation menu, use the value prop instead.
    default_value: Var[str]

    # Callback fired when the value changes.
    on_value_change: EventHandler[passthrough_event_spec(str, dict)]

    # The orientation of the navigation menu.
    orientation: Var[LiteralNavigationMenuOrientation]

    # How long to wait before opening the navigation menu. Specified in milliseconds. Defaults to 50.
    delay: Var[int]

    # How long to wait before closing the navigation menu. Specified in milliseconds. Defaults to 50.
    close_delay: Var[int]

    # Event handler called after any animations complete when the navigation menu is closed.
    on_open_change_complete: EventHandler[passthrough_event_spec(bool)]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the navigation menu root component.

        Returns:
            The component.
        """
        props["data-slot"] = "navigation-menu"
        cls.set_class_name(ClassNames.ROOT, props)
        return super().create(*children, **props)


class NavigationMenuList(NavigationMenuBaseComponent):
    """Contains a list of navigation menu items. Renders a <div> element."""

    tag = "NavigationMenu.List"

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the navigation menu list component.

        Returns:
            The component.
        """
        props["data-slot"] = "navigation-menu-list"
        cls.set_class_name(ClassNames.LIST, props)
        return super().create(*children, **props)


class NavigationMenuItem(NavigationMenuBaseComponent):
    """An individual navigation menu item. Renders a <div> element."""

    tag = "NavigationMenu.Item"

    value: Var[str]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the navigation menu item component.

        Returns:
            The component.
        """
        props["data-slot"] = "navigation-menu-item"
        cls.set_class_name(ClassNames.ITEM, props)
        return super().create(*children, **props)


class NavigationMenuTrigger(NavigationMenuBaseComponent):
    """Opens the navigation menu popup when hovered or clicked, revealing the associated content. Renders a <button> element."""

    tag = "NavigationMenu.Trigger"

    # Whether the component should ignore user interaction. Defaults to False.
    disabled: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the navigation menu trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "navigation-menu-trigger"
        cls.set_class_name(ClassNames.TRIGGER, props)
        return super().create(*children, **props)


class NavigationMenuContent(NavigationMenuBaseComponent):
    """A container for the content of the navigation menu item that is moved into the popup when the item is active. Renders a <div> element."""

    tag = "NavigationMenu.Content"

    # Whether to keep the HTML element in the DOM while the content is hidden. Defaults to False.
    keep_mounted: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the navigation menu content component.

        Returns:
            The component.
        """
        props["data-slot"] = "navigation-menu-content"
        cls.set_class_name(ClassNames.CONTENT, props)
        return super().create(*children, **props)


class NavigationMenuLink(NavigationMenuBaseComponent):
    """A link in the navigation menu that can be used to navigate to a different page or section. Renders an <a> element."""

    tag = "NavigationMenu.Link"

    active: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the navigation menu link component.

        Returns:
            The component.
        """
        props["data-slot"] = "navigation-menu-link"
        cls.set_class_name(ClassNames.LINK, props)
        return super().create(*children, **props)


class NavigationMenuIcon(NavigationMenuBaseComponent):
    """An icon that indicates that the trigger button opens a menu. Renders a <span> element."""

    tag = "NavigationMenu.Icon"

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the navigation menu icon component.

        Returns:
            The component.
        """
        props["data-slot"] = "navigation-menu-icon"
        cls.set_class_name(ClassNames.ICON, props)
        return super().create(*children, **props)


class NavigationMenuPortal(NavigationMenuBaseComponent):
    """A portal element that moves the content to a different part of the DOM."""

    tag = "NavigationMenu.Portal"

    # A parent element to render the portal element into.
    container: Var[str]

    # Whether to keep the portal mounted in the DOM while the content is hidden. Defaults to False.
    keep_mounted: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the navigation menu portal component.

        Returns:
            The component.
        """
        props["data-slot"] = "navigation-menu-portal"
        cls.set_class_name(ClassNames.PORTAL, props)
        return super().create(*children, **props)


class NavigationMenuPositioner(NavigationMenuBaseComponent):
    """Positions the content against the trigger. Renders a <div> element."""

    tag = "NavigationMenu.Positioner"

    # Determines how to handle collisions when positioning the content.
    collision_avoidance: Var[bool | LiteralCollisionAvoidance]

    align: Var[LiteralAlign]

    # Additional offset along the alignment axis in pixels. Defaults to 0.
    align_offset: Var[int]

    # Which side of the anchor element to align the content against. May automatically change to avoid collisions. Defaults to "bottom".
    side: Var[LiteralSide]

    # Distance between the anchor and the content in pixels. Defaults to 0.
    side_offset: Var[int]

    # Minimum distance to maintain between the arrow and the edges of the content. Use it to prevent the arrow element from hanging out of the rounded corners of a content. Defaults to 5.
    arrow_padding: Var[int]

    # Additional space to maintain from the edge of the collision boundary. Defaults to 5.
    collision_padding: Var[int]

    # An element or a rectangle that delimits the area that the content is confined to. Defaults to the "clipping-ancestors".
    collision_boundary: Var[str]

    # Whether to maintain the content in the viewport after the anchor element was scrolled out of view. Defaults to False.
    sticky: Var[bool]

    # Whether to disable the content tracking any layout shift of its positioning anchor. Defaults to False.
    disable_anchor_tracking: Var[bool]

    # Determines which CSS position property to use. Defaults to "absolute".
    position_method: Var[LiteralPositionMethod]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the navigation menu positioner component.

        Returns:
            The component.
        """
        props["data-slot"] = "navigation-menu-positioner"
        props.setdefault("side_offset", 10)
        cls.set_class_name(ClassNames.POSITIONER, props)
        return super().create(*children, **props)


class NavigationMenuPopup(NavigationMenuBaseComponent):
    """A container for the navigation menu content. Renders a <div> element."""

    tag = "NavigationMenu.Popup"

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the navigation menu popup component.

        Returns:
            The component.
        """
        props["data-slot"] = "navigation-menu-popup"
        cls.set_class_name(ClassNames.POPUP, props)
        return super().create(*children, **props)


class NavigationMenuViewport(NavigationMenuBaseComponent):
    """An optional viewport element that masks the content when it overflows. Renders a <div> element."""

    tag = "NavigationMenu.Viewport"

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the navigation menu viewport component.

        Returns:
            The component.
        """
        props["data-slot"] = "navigation-menu-viewport"
        cls.set_class_name(ClassNames.VIEWPORT, props)
        return super().create(*children, **props)


class NavigationMenuArrow(NavigationMenuBaseComponent):
    """Displays an element positioned against the navigation menu anchor. Renders a <div> element."""

    tag = "NavigationMenu.Arrow"

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the navigation menu arrow component.

        Returns:
            The component.
        """
        props["data-slot"] = "navigation-menu-arrow"
        cls.set_class_name(ClassNames.ARROW, props)
        return super().create(*children, **props)


class NavigationMenuBackdrop(NavigationMenuBaseComponent):
    """An optional backdrop element that can be used to close the navigation menu. Renders a <div> element."""

    tag = "NavigationMenu.Backdrop"

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the navigation menu backdrop component.

        Returns:
            The component.
        """
        props["data-slot"] = "navigation-menu-backdrop"
        cls.set_class_name(ClassNames.BACKDROP, props)
        return super().create(*children, **props)


class NavigationMenu(ComponentNamespace):
    """Namespace for NavigationMenu components."""

    root = staticmethod(NavigationMenuRoot.create)
    list = staticmethod(NavigationMenuList.create)
    item = staticmethod(NavigationMenuItem.create)
    trigger = staticmethod(NavigationMenuTrigger.create)
    content = staticmethod(NavigationMenuContent.create)
    link = staticmethod(NavigationMenuLink.create)
    icon = staticmethod(NavigationMenuIcon.create)
    portal = staticmethod(NavigationMenuPortal.create)
    positioner = staticmethod(NavigationMenuPositioner.create)
    popup = staticmethod(NavigationMenuPopup.create)
    viewport = staticmethod(NavigationMenuViewport.create)
    arrow = staticmethod(NavigationMenuArrow.create)
    backdrop = staticmethod(NavigationMenuBackdrop.create)
    class_names = ClassNames


navigation_menu = NavigationMenu()
