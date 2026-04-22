"""Custom popover component."""

from typing import Literal

from reflex.components.component import Component, ComponentNamespace
from reflex.event import EventHandler, passthrough_event_spec
from reflex.utils.imports import ImportVar
from reflex.vars.base import Var
from reflex_components_internal.components.base_ui import PACKAGE_NAME, BaseUIComponent
from reflex_components_internal.utils.twmerge import cn

LiteralAlign = Literal["start", "center", "end"]
LiteralSide = Literal["bottom", "inline-end", "inline-start", "left", "right", "top"]
LiteralPosition = Literal["absolute", "fixed"]


class ClassNames:
    """Class names for popover components."""

    ROOT = ""
    TRIGGER = ""
    BACKDROP = ""
    PORTAL = ""
    POSITIONER = ""
    POPUP = "origin-(--transform-origin) rounded-ui-xl p-1 border border-secondary-a4 bg-secondary-1 shadow-large transition-[transform,scale,opacity] data-[ending-style]:scale-95 data-[starting-style]:scale-95 data-[ending-style]:opacity-0 data-[starting-style]:opacity-0 outline-none min-w-36 flex flex-col gap-2"
    ARROW = "data-[side=bottom]:top-[-8px] data-[side=left]:right-[-13px] data-[side=left]:rotate-90 data-[side=right]:left-[-13px] data-[side=right]:-rotate-90 data-[side=top]:bottom-[-8px] data-[side=top]:rotate-180"
    TITLE = "text-lg font-semibold text-secondary-12"
    DESCRIPTION = "text-sm text-secondary-11 font-[450]"
    CLOSE = ""


class PopoverBaseComponent(BaseUIComponent):
    """Base component for popover components."""

    library = f"{PACKAGE_NAME}/popover"

    @property
    def import_var(self):
        """Return the import variable for the popover component."""
        return ImportVar(tag="Popover", package_path="", install=False)


class PopoverRoot(PopoverBaseComponent):
    """Groups all parts of the popover. Doesn't render its own HTML element."""

    tag = "Popover.Root"

    # Whether the popover is initially open. To render a controlled popover, use the open prop instead. Defaults to False.
    default_open: Var[bool]

    # Whether the popover is currently open.
    open: Var[bool]

    # Event handler called when the popover is opened or closed
    on_open_change: EventHandler[passthrough_event_spec(bool, dict)]

    # Event handler called after any animations complete when the popover is opened or closed.
    on_open_change_complete: EventHandler[passthrough_event_spec(bool)]

    # Determines if the popover enters a modal state when open.
    # - True: user interaction is limited to just the popover: focus is trapped, document page scroll is locked, and pointer interactions on outside elements are disabled.
    # - False: user interaction with the rest of the document is allowed.
    # - 'trap-focus': focus is trapped inside the popover, but document page scroll is not locked and pointer interactions outside of it remain enabled.
    modal: Var[bool | Literal["trap-focus"]]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the popover root component.

        Returns:
            The component.
        """
        props["data-slot"] = "popover"
        return super().create(*children, **props)


class PopoverTrigger(PopoverBaseComponent):
    """A button that opens the popover. Renders a <button> element."""

    tag = "Popover.Trigger"

    # Whether the component renders a native <button> element when replacing it via the render prop. Set to false if the rendered element is not a button (e.g. <div>).. Defaults to True.
    native_button: Var[bool]

    # Whether the popover should also open when the trigger is hovered. Defaults to False.
    open_on_hover: Var[bool]

    # How long to wait before the popover may be opened on hover. Specified in milliseconds. Requires the open_on_hover prop. Defaults to 300.
    delay: Var[int]

    # How long to wait before closing the popover that was opened on hover. Specified in milliseconds. Requires the open_on_hover prop. Defaults to 0.
    close_delay: Var[int]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the popover trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "popover-trigger"
        cls.set_class_name(ClassNames.TRIGGER, props)
        return super().create(*children, **props)


class PopoverBackdrop(PopoverBaseComponent):
    """An overlay displayed beneath the popup. Renders a <div> element."""

    tag = "Popover.Backdrop"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the popover backdrop component.

        Returns:
            The component.
        """
        props["data-slot"] = "popover-backdrop"
        cls.set_class_name(ClassNames.BACKDROP, props)
        return super().create(*children, **props)


class PopoverPortal(PopoverBaseComponent):
    """A portal element that moves the popup to a different part of the DOM. By default, the portal element is appended to <body>."""

    tag = "Popover.Portal"

    # A parent element to render the portal element into.
    container: Var[str]

    # Whether to keep the portal mounted in the DOM while the popup is hidden. Defaults to False.
    keep_mounted: Var[bool]


class PopoverPositioner(PopoverBaseComponent):
    """Positions the popover against the trigger. Renders a <div> element."""

    tag = "Popover.Positioner"

    # How to align the popup relative to the specified side. Defaults to "center".
    align: Var[LiteralAlign]

    # Additional offset along the alignment axis in pixels. Defaults to 0.
    align_offset: Var[int]

    # Which side of the anchor element to align the popup against. May automatically change to avoid collisions Defaults to "bottom".
    side: Var[LiteralSide]

    # Distance between the anchor and the popup in pixels. Defaults to 0.
    side_offset: Var[int]

    # Minimum distance to maintain between the arrow and the edges of the popup. Use it to prevent the arrow element from hanging out of the rounded corners of a popup. Defaults to 5.
    arrow_padding: Var[int]

    # An element to position the popup against. By default, the popup will be positioned against the trigger.
    anchor: Var[str]

    # An element or a rectangle that delimits the area that the popup is confined to. Defaults to "clipping-ancestors".
    collision_boundary: Var[str]

    # Additional space to maintain from the edge of the collision boundary. Defaults to 5.
    collision_padding: Var[int | list[int]]

    # Whether to maintain the popup in the viewport after the anchor element was scrolled out of view. Defaults to False.
    sticky: Var[bool]

    # Determines which CSS position property to use. Defaults to "absolute".
    position_method: Var[LiteralPosition]

    # Whether to disable the popup tracking any layout shift of its positioning anchor. Defaults to False.
    disable_anchor_tracking: Var[bool]

    # Determines how to handle collisions when positioning the popup.
    collision_avoidance: Var[str]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the popover positioner component.

        Returns:
            The component.
        """
        props["data-slot"] = "popover-positioner"
        props.setdefault("side_offset", 4)
        cls.set_class_name(ClassNames.POSITIONER, props)
        return super().create(*children, **props)


class PopoverPopup(PopoverBaseComponent):
    """A container for the popover contents. Renders a <div> element."""

    tag = "Popover.Popup"

    # Determines the element to focus when the popover is opened. By default, the first focusable element is focused.
    initial_focus: Var[str]

    # Determines the element to focus when the popover is closed. By default, focus returns to the trigger.
    final_focus: Var[str]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the popover popup component.

        Returns:
            The component.
        """
        props["data-slot"] = "popover-popup"
        cls.set_class_name(ClassNames.POPUP, props)
        return super().create(*children, **props)


class PopoverArrow(PopoverBaseComponent):
    """Displays an element positioned against the popover anchor. Renders a <div> element."""

    tag = "Popover.Arrow"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the popover arrow component.

        Returns:
            The component.
        """
        props["data-slot"] = "popover-arrow"
        cls.set_class_name(ClassNames.ARROW, props)
        return super().create(*children, **props)


class PopoverTitle(PopoverBaseComponent):
    """A heading that labels the popover. Renders an <h2> element."""

    tag = "Popover.Title"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the popover title component.

        Returns:
            The component.
        """
        props["data-slot"] = "popover-title"
        cls.set_class_name(ClassNames.TITLE, props)
        return super().create(*children, **props)


class PopoverDescription(PopoverBaseComponent):
    """A paragraph with additional information about the popover. Renders a <p> element."""

    tag = "Popover.Description"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the popover description component.

        Returns:
            The component.
        """
        props["data-slot"] = "popover-description"
        cls.set_class_name(ClassNames.DESCRIPTION, props)
        return super().create(*children, **props)


class PopoverClose(PopoverBaseComponent):
    """A button that closes the popover. Renders a <button> element."""

    tag = "Popover.Close"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the popover close component.

        Returns:
            The component.
        """
        props["data-slot"] = "popover-close"
        cls.set_class_name(ClassNames.CLOSE, props)
        return super().create(*children, **props)


class HighLevelPopover(PopoverRoot):
    """High level wrapper for the Popover component."""

    # Popover props
    trigger: Var[Component | None]
    content: Var[str | Component | None]
    title: Var[str | Component | None]
    description: Var[str | Component | None]

    # Props for different component parts
    _trigger_props = {"open_on_hover", "delay", "close_delay", "native_button"}
    _positioner_props = {
        "align",
        "align_offset",
        "side",
        "side_offset",
        "arrow_padding",
        "collision_padding",
        "collision_boundary",
        "sticky",
        "position_method",
        "disable_anchor_tracking",
        "anchor",
        "collision_avoidance",
    }
    _portal_props = {"container", "keep_mounted"}

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create a popover component.

        Args:
            *children: Additional children to include in the popover.
            **props: Additional properties to apply to the popover component.

        Returns:
            The popover component.
        """
        # Extract props for different parts
        trigger_props = {k: props.pop(k) for k in cls._trigger_props & props.keys()}
        positioner_props = {
            k: props.pop(k) for k in cls._positioner_props & props.keys()
        }
        portal_props = {k: props.pop(k) for k in cls._portal_props & props.keys()}

        trigger = props.pop("trigger", None)
        content = props.pop("content", None)
        title = props.pop("title", None)
        description = props.pop("description", None)
        class_name = props.pop("class_name", "")

        return PopoverRoot.create(
            PopoverTrigger.create(render_=trigger, **trigger_props)
            if trigger is not None
            else None,
            PopoverPortal.create(
                PopoverPositioner.create(
                    PopoverPopup.create(
                        PopoverTitle.create(title) if title is not None else None,
                        (
                            PopoverDescription.create(description)
                            if description is not None
                            else None
                        ),
                        content,
                        *children,
                        class_name=cn(ClassNames.POPUP, class_name),
                    ),
                    **positioner_props,
                ),
                **portal_props,
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


class Popover(ComponentNamespace):
    """Namespace for Popover components."""

    root = staticmethod(PopoverRoot.create)
    trigger = staticmethod(PopoverTrigger.create)
    backdrop = staticmethod(PopoverBackdrop.create)
    portal = staticmethod(PopoverPortal.create)
    positioner = staticmethod(PopoverPositioner.create)
    popup = staticmethod(PopoverPopup.create)
    arrow = staticmethod(PopoverArrow.create)
    title = staticmethod(PopoverTitle.create)
    description = staticmethod(PopoverDescription.create)
    close = staticmethod(PopoverClose.create)
    class_names = ClassNames
    __call__ = staticmethod(HighLevelPopover.create)


popover = Popover()
