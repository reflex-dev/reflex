"""Custom drawer component."""

from collections.abc import Sequence
from typing import Literal

from reflex_components_core.el.elements.typography import Div

from reflex.components.component import Component, ComponentNamespace
from reflex.event import EventHandler, passthrough_event_spec
from reflex.utils.imports import ImportVar
from reflex.vars.base import Var
from reflex_components_internal.components.base.button import button
from reflex_components_internal.components.base_ui import PACKAGE_NAME, BaseUIComponent
from reflex_components_internal.components.icons.hugeicon import hi

LiteralSwipeDirectionType = Literal["up", "down", "left", "right"]


class ClassNames:
    """Class names for the drawer component."""

    ROOT = ""
    TRIGGER = ""
    PORTAL = ""
    BACKDROP = "fixed inset-0 bg-black opacity-40 transition-all duration-150 data-[ending-style]:opacity-0 data-[starting-style]:opacity-0 dark:opacity-80"
    VIEWPORT = "fixed inset-0 flex items-end justify-center"
    POPUP = "w-full max-h-[80vh] -mb-[3rem] rounded-t-2xl border border-secondary-a4 bg-secondary-1 px-6 pt-4 pb-[calc(1.5rem+env(safe-area-inset-bottom,0px)+3rem)] text-secondary-12 overflow-y-auto overscroll-contain touch-auto [transform:translateY(var(--drawer-swipe-movement-y))] transition-transform duration-[450ms] ease-[cubic-bezier(0.32,0.72,0,1)] data-[swiping]:select-none data-[ending-style]:[transform:translateY(calc(100%-3rem+2px))] data-[starting-style]:[transform:translateY(calc(100%-3rem+2px))] data-[ending-style]:duration-[calc(var(--drawer-swipe-strength)*400ms)]"
    CONTENT = "mx-auto w-full max-w-[32rem]"
    TITLE = "text-2xl font-semibold text-secondary-12"
    DESCRIPTION = "text-sm text-secondary-11"
    CLOSE = ""
    HANDLE = "w-12 h-1 mx-auto mb-4 rounded-full bg-secondary-a6"
    HEADER = "flex flex-col gap-2 pb-4"
    SWIPE_AREA = ""
    PROVIDER = ""
    INDENT_BACKGROUND = ""
    INDENT = ""


class DrawerBaseComponent(BaseUIComponent):
    """Base component for drawer components."""

    library = f"{PACKAGE_NAME}/drawer"

    @property
    def import_var(self):
        """Return the import variable for the drawer component."""
        return ImportVar(tag="Drawer", package_path="", install=False)


class DrawerRoot(DrawerBaseComponent):
    """The Root component of a Drawer, contains all parts of a drawer."""

    tag = "Drawer.Root"

    # The open state of the drawer when it is initially rendered. Use when you do not need to control its open state.
    default_open: Var[bool]

    # Whether the drawer is currently open.
    open: Var[bool]

    # Event handler called when the drawer is opened or closed.
    on_open_change: EventHandler[passthrough_event_spec(bool, dict)]

    # Direction of the swipe gesture to dismiss. Defaults to 'down'.
    swipe_direction: Var[LiteralSwipeDirectionType]

    # Determines if the drawer enters a modal state when open.
    modal: Var[bool | Literal["trap-focus"]]

    # Determines whether pointer dismissal (clicking outside) is disabled. Defaults to False.
    disable_pointer_dismissal: Var[bool]

    # Event handler called after any animations complete when the drawer is opened or closed.
    on_open_change_complete: EventHandler[passthrough_event_spec(bool)]

    # Array of snap points. Numbers between 0 and 1 represent fractions of the viewport height, and numbers greater than 1 are treated as pixel values. String values support `px` and `rem` units.
    snap_points: Sequence[str | float] | None

    # Current active snap point.
    snap_point: Var[str | float | None]

    # Event handler called when the snap point changes.
    on_snap_point_change: EventHandler[passthrough_event_spec(str | float | None)]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the drawer root component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-root"
        cls.set_class_name(ClassNames.ROOT, props)
        return super().create(*children, **props)


class DrawerTrigger(DrawerBaseComponent):
    """A button that opens the drawer. Renders a <button> element."""

    tag = "Drawer.Trigger"

    # Whether the component renders a native <button> element when replacing it via the render prop.
    native_button: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the drawer trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-trigger"
        cls.set_class_name(ClassNames.TRIGGER, props)
        return super().create(*children, **props)


class DrawerPortal(DrawerBaseComponent):
    """A portal element that moves the popup to a different part of the DOM. By default, the portal element is appended to <body>."""

    tag = "Drawer.Portal"

    # A parent element to render the portal element into.
    container: Var[str]

    # Whether to keep the portal mounted in the DOM while the popup is hidden. Defaults to False.
    keep_mounted: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the drawer portal component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-portal"
        cls.set_class_name(ClassNames.PORTAL, props)
        return super().create(*children, **props)


class DrawerBackdrop(DrawerBaseComponent):
    """An overlay displayed beneath the popup. Renders a <div> element."""

    tag = "Drawer.Backdrop"

    # Whether the backdrop is forced to render even when nested. Defaults to False.
    force_render: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the drawer backdrop component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-backdrop"
        cls.set_class_name(ClassNames.BACKDROP, props)
        return super().create(*children, **props)


class DrawerViewport(DrawerBaseComponent):
    """A viewport container for the drawer popup. Renders a <div> element."""

    tag = "Drawer.Viewport"

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the drawer viewport component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-viewport"
        cls.set_class_name(ClassNames.VIEWPORT, props)
        return super().create(*children, **props)


class DrawerPopup(DrawerBaseComponent):
    """A container for the drawer contents. Renders a <div> element."""

    tag = "Drawer.Popup"

    # Determines the element to focus when the drawer is opened. By default, the first focusable element is focused.
    initial_focus: Var[str]

    # Determines the element to focus when the drawer is closed. By default, focus returns to the trigger.
    final_focus: Var[str]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the drawer popup component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-popup"
        cls.set_class_name(ClassNames.POPUP, props)
        return super().create(*children, **props)


class DrawerContent(DrawerBaseComponent):
    """Content within the drawer popup. Allows text selection without swipe interference."""

    tag = "Drawer.Content"

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the drawer content component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-content"
        cls.set_class_name(ClassNames.CONTENT, props)
        return super().create(*children, **props)


class DrawerTitle(DrawerBaseComponent):
    """A heading that labels the drawer. Renders an <h2> element."""

    tag = "Drawer.Title"

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the drawer title component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-title"
        cls.set_class_name(ClassNames.TITLE, props)
        return super().create(*children, **props)


class DrawerDescription(DrawerBaseComponent):
    """A paragraph with additional information about the drawer. Renders a <p> element."""

    tag = "Drawer.Description"

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the drawer description component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-description"
        cls.set_class_name(ClassNames.DESCRIPTION, props)
        return super().create(*children, **props)


class DrawerClose(DrawerBaseComponent):
    """A button that closes the drawer. Renders a <button> element."""

    tag = "Drawer.Close"

    # Whether the component renders a native <button> element when replacing it via the render prop.
    native_button: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the drawer close component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-close"
        cls.set_class_name(ClassNames.CLOSE, props)
        return super().create(*children, **props)


class DrawerSwipeArea(DrawerBaseComponent):
    """An area that responds to swipe gestures to dismiss the drawer."""

    tag = "Drawer.SwipeArea"

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the drawer swipe area component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-swipe-area"
        cls.set_class_name(ClassNames.SWIPE_AREA, props)
        return super().create(*children, **props)


class DrawerProvider(DrawerBaseComponent):
    """Provides shared context for nested drawers with indent effects."""

    tag = "Drawer.Provider"

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the drawer provider component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-provider"
        cls.set_class_name(ClassNames.PROVIDER, props)
        return super().create(*children, **props)


class DrawerIndentBackground(DrawerBaseComponent):
    """Background element for the indent effect when nested drawers are open."""

    tag = "Drawer.IndentBackground"

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the drawer indent background component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-indent-background"
        cls.set_class_name(ClassNames.INDENT_BACKGROUND, props)
        return super().create(*children, **props)


class DrawerIndent(DrawerBaseComponent):
    """Container for the indent effect. Wraps the drawer root."""

    tag = "Drawer.Indent"

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the drawer indent component.

        Returns:
            The component.
        """
        props["data-slot"] = "drawer-indent"
        cls.set_class_name(ClassNames.INDENT, props)
        return super().create(*children, **props)


class HighLevelDrawer(DrawerRoot):
    """High level wrapper for the Drawer component."""

    # The trigger component that opens the drawer.
    trigger: Var[Component | None]

    # The content to display inside the drawer body.
    content: Var[str | Component | None]

    # The title displayed in the drawer header.
    title: Var[str | Component | None]

    # The description displayed below the drawer title.
    description: Var[str | Component | None]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the high level drawer component.

        Returns:
            The component.
        """
        trigger = props.pop("trigger", None)
        content = props.pop("content", None)
        title = props.pop("title", None)
        description = props.pop("description", None)
        class_name = props.pop("class_name", "")

        return DrawerRoot.create(
            DrawerTrigger.create(render_=trigger) if trigger is not None else None,
            DrawerPortal.create(
                DrawerBackdrop.create(),
                DrawerViewport.create(
                    DrawerPopup.create(
                        Div.create(
                            class_name=ClassNames.HANDLE,
                        ),
                        DrawerContent.create(
                            Div.create(
                                Div.create(
                                    DrawerTitle.create(title)
                                    if title is not None
                                    else None,
                                    DrawerClose.create(
                                        render_=button(
                                            hi("Cancel01Icon"),
                                            variant="ghost",
                                            size="icon-sm",
                                            class_name="text-secondary-11",
                                        ),
                                    ),
                                    class_name="flex flex-row justify-between items-baseline gap-1",
                                ),
                                (
                                    DrawerDescription.create(description)
                                    if description is not None
                                    else None
                                ),
                                data_slot="drawer-header",
                                class_name=ClassNames.HEADER,
                            ),
                            content,
                            *children,
                        ),
                        class_name=class_name,
                    ),
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
    backdrop = staticmethod(DrawerBackdrop.create)
    viewport = staticmethod(DrawerViewport.create)
    popup = staticmethod(DrawerPopup.create)
    content = staticmethod(DrawerContent.create)
    title = staticmethod(DrawerTitle.create)
    description = staticmethod(DrawerDescription.create)
    close = staticmethod(DrawerClose.create)
    swipe_area = staticmethod(DrawerSwipeArea.create)
    provider = staticmethod(DrawerProvider.create)
    indent_background = staticmethod(DrawerIndentBackground.create)
    indent = staticmethod(DrawerIndent.create)
    class_names = ClassNames
    __call__ = staticmethod(HighLevelDrawer.create)


drawer = Drawer()
