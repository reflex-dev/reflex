"""Custom drawer component."""

from collections.abc import Sequence
from typing import Literal

from reflex.components.component import Component, ComponentNamespace
from reflex.event import EventHandler, passthrough_event_spec
from reflex.vars.base import Var
from reflex_ui.components.component import CoreComponent

LiteralDirectionType = Literal["top", "bottom", "left", "right"]


class ClassNames:
    """Class names for the drawer component."""

    ROOT = ""
    TRIGGER = ""
    PORTAL = ""
    CONTENT = "fixed right-0 bottom-0 z-50 bg-secondary-1 max-w-96 border-l border-secondary-a4 size-full flex"
    OVERLAY = "fixed inset-0 z-50 bg-black/50"
    CLOSE = ""
    TITLE = "text-2xl font-semibold text-secondary-12"
    DESCRIPTION = "text-sm text-secondary-11"
    HANDLE = ""


class DrawerBaseComponent(CoreComponent):
    """Base component for drawer components."""

    library = "vaul-base@0.0.6"


class DrawerRoot(DrawerBaseComponent):
    """The Root component of a Drawer, contains all parts of a drawer."""

    tag = "Drawer.Root"

    # The open state of the drawer when it is initially rendered. Use when you do not need to control its open state.
    default_open: Var[bool]

    # Whether the drawer is open or not.
    open: Var[bool]

    # Fires when the drawer is opened or closed.
    on_open_change: EventHandler[passthrough_event_spec(bool)]

    # When False, it allows interaction with elements outside of the drawer without closing it. Defaults to True.
    modal: Var[bool]

    # Direction of the drawer. This adjusts the animations and the drag direction. Defaults to "bottom"
    direction: Var[LiteralDirectionType]

    # Gets triggered after the open or close animation ends, it receives an open argument with the open state of the drawer by the time the function was triggered.
    on_animation_end: EventHandler[passthrough_event_spec(bool)]

    # When False, dragging, clicking outside, pressing esc, etc. will not close the drawer. Use this in combination with the open prop, otherwise you won't be able to open/close the drawer.
    dismissible: Var[bool]

    # When True, dragging will only be possible by the handle.
    handle_only: Var[bool]

    # Container element to render the portal into. Defaults to document.body.
    container: Var[str]

    # Whether to reposition inputs when the drawer opens. Defaults to True.
    reposition_inputs: Var[bool]

    # Array of numbers from 0 to 100 that corresponds to % of the screen a given snap point should take up. Should go from least visible. Also Accept px values, which doesn't take screen height into account.
    snap_points: Sequence[str | float] | None

    # Current active snap point.
    active_snap_point: Var[bool]

    # Function to set the active snap point.
    set_active_snap_point: EventHandler[passthrough_event_spec(int)]

    # Index of a snap point from which the overlay fade should be applied. Defaults to the last snap point.
    fade_from_index: Var[int]

    # Whether to snap to sequential points.
    snap_to_sequential_point: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the drawer root component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-root"
        cls.set_class_name(ClassNames.ROOT, props)
        return super().create(*children, **props)


class DrawerTrigger(DrawerBaseComponent):
    """The button that opens the drawer."""

    tag = "Drawer.Trigger"

    # Render the trigger as a child. Defaults to False.
    as_child: Var[bool]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the drawer trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-trigger"
        cls.set_class_name(ClassNames.TRIGGER, props)
        return super().create(*children, **props)


class DrawerPortal(DrawerBaseComponent):
    """Portals your drawer into the body."""

    tag = "Drawer.Portal"

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the drawer portal component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-portal"
        cls.set_class_name(ClassNames.PORTAL, props)
        return super().create(*children, **props)


class DrawerContent(DrawerBaseComponent):
    """Content that should be rendered in the drawer."""

    tag = "Drawer.Content"

    # Render the content as a child. Defaults to False.
    as_child: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the drawer content component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-content"
        cls.set_class_name(ClassNames.CONTENT, props)
        return super().create(*children, **props)


class DrawerOverlay(DrawerBaseComponent):
    """A layer that covers the inert portion of the view when the drawer is open."""

    tag = "Drawer.Overlay"

    # Render the overlay as a child. Defaults to False.
    as_child: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the drawer overlay component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-overlay"
        cls.set_class_name(ClassNames.OVERLAY, props)
        return super().create(*children, **props)


class DrawerClose(DrawerBaseComponent):
    """A button that closes the drawer."""

    tag = "Drawer.Close"

    # Render the close button as a child. Defaults to False.
    as_child: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the drawer close component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-close"
        cls.set_class_name(ClassNames.CLOSE, props)
        return super().create(*children, **props)


class DrawerTitle(DrawerBaseComponent):
    """An optional accessible title to be announced when the drawer is opened."""

    tag = "Drawer.Title"

    # Render the title as a child. Defaults to False.
    as_child: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the drawer title component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-title"
        cls.set_class_name(ClassNames.TITLE, props)
        return super().create(*children, **props)


class DrawerDescription(DrawerBaseComponent):
    """An optional accessible description to be announced when the drawer is opened."""

    tag = "Drawer.Description"

    # Render the description as a child. Defaults to False.
    as_child: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the drawer description component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-description"
        cls.set_class_name(ClassNames.DESCRIPTION, props)
        return super().create(*children, **props)


class DrawerHandle(DrawerBaseComponent):
    """An optional handle to drag the drawer."""

    tag = "Drawer.Handle"

    alias = "Vaul" + tag

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the drawer handle component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-handle"
        cls.set_class_name(ClassNames.HANDLE, props)
        return super().create(*children, **props)


class HighLevelDrawer(DrawerRoot):
    """High level wrapper for the Drawer component."""

    # Drawer props
    trigger: Var[Component | None]
    content: Var[str | Component | None]
    title: Var[str | Component | None]
    description: Var[str | Component | None]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the high level drawer component.

        Returns:
            The component.
        """
        trigger = props.pop("trigger", None)
        content = props.pop("content", None)
        title = props.pop("title", None)
        description = props.pop("description", None)

        return super().create(
            DrawerTrigger.create(render_=trigger) if trigger is not None else None,
            DrawerPortal.create(
                DrawerOverlay.create(),
                DrawerContent.create(
                    DrawerTitle.create(title) if title is not None else None,
                    (
                        DrawerDescription.create(description)
                        if description is not None
                        else None
                    ),
                    content,
                    *children,
                ),
            ),
            **props,
        )

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "trigger",
            "content",
            "title",
            "description",
        ]


class Drawer(ComponentNamespace):
    """A namespace for Drawer components."""

    root = staticmethod(DrawerRoot.create)
    trigger = staticmethod(DrawerTrigger.create)
    portal = staticmethod(DrawerPortal.create)
    content = staticmethod(DrawerContent.create)
    overlay = staticmethod(DrawerOverlay.create)
    close = staticmethod(DrawerClose.create)
    title = staticmethod(DrawerTitle.create)
    description = staticmethod(DrawerDescription.create)
    handle = staticmethod(DrawerHandle.create)
    class_names = ClassNames
    __call__ = staticmethod(HighLevelDrawer.create)


drawer = Drawer()
