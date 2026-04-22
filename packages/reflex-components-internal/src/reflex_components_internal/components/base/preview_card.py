"""Custom preview card component."""

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
    """Class names for preview card components."""

    ROOT = ""
    TRIGGER = ""
    BACKDROP = ""
    PORTAL = ""
    POSITIONER = ""
    POPUP = "origin-(--transform-origin) rounded-ui-xl p-3 border border-secondary-a4 bg-secondary-1 shadow-large transition-[transform,scale,opacity] data-[ending-style]:scale-95 data-[starting-style]:scale-95 data-[ending-style]:opacity-0 data-[starting-style]:opacity-0 outline-none min-w-64 flex flex-col gap-3"
    ARROW = "data-[side=bottom]:top-[-8px] data-[side=left]:right-[-13px] data-[side=left]:rotate-90 data-[side=right]:left-[-13px] data-[side=right]:-rotate-90 data-[side=top]:bottom-[-8px] data-[side=top]:rotate-180"


class PreviewCardBaseComponent(BaseUIComponent):
    """Base component for preview card components."""

    library = f"{PACKAGE_NAME}/preview-card"

    @property
    def import_var(self):
        """Return the import variable for the preview card component."""
        return ImportVar(tag="PreviewCard", package_path="", install=False)


class PreviewCardRoot(PreviewCardBaseComponent):
    """Groups all parts of the preview card. Doesn't render its own HTML element."""

    tag = "PreviewCard.Root"

    # Whether the preview card is initially open. To render a controlled preview card, use the `open` prop instead. Defaults to false.
    default_open: Var[bool]

    # Whether the preview card is currently open.
    open: Var[bool]

    # Event handler called when the preview card is opened or closed.
    on_open_change: EventHandler[passthrough_event_spec(bool, dict)]

    # Event handler called after any animations complete when the preview card is opened or closed.
    on_open_change_complete: EventHandler[passthrough_event_spec(bool)]

    # How long to wait before the preview card opens. Specified in milliseconds. Defaults to 600.
    delay: Var[int]

    # How long to wait before closing the preview card that was opened on hover. Specified in milliseconds. Defaults to 300.
    close_delay: Var[int]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the preview card root component.

        Returns:
            The component.
        """
        props["data-slot"] = "preview-card"
        return super().create(*children, **props)


class PreviewCardTrigger(PreviewCardBaseComponent):
    """A button that opens the preview card. Renders a <button> element."""

    tag = "PreviewCard.Trigger"

    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the preview card trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "preview-card-trigger"
        cls.set_class_name(ClassNames.TRIGGER, props)
        return super().create(*children, **props)


class PreviewCardBackdrop(PreviewCardBaseComponent):
    """An overlay displayed beneath the popup. Renders a <div> element."""

    tag = "PreviewCard.Backdrop"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the preview card backdrop component.

        Returns:
            The component.
        """
        props["data-slot"] = "preview-card-backdrop"
        cls.set_class_name(ClassNames.BACKDROP, props)
        return super().create(*children, **props)


class PreviewCardPortal(PreviewCardBaseComponent):
    """A portal element that moves the popup to a different part of the DOM. By default, the portal element is appended to <body>."""

    tag = "PreviewCard.Portal"

    # A parent element to render the portal element into.
    container: Var[str]

    # Whether to keep the portal mounted in the DOM while the popup is hidden. Defaults to false.
    keep_mounted: Var[bool]


class PreviewCardPositioner(PreviewCardBaseComponent):
    """Positions the preview card against the trigger. Renders a <div> element."""

    tag = "PreviewCard.Positioner"

    # Determines how to handle collisions when positioning the popup.
    collision_avoidance: Var[str]

    # How to align the popup relative to the specified side. Defaults to center.
    align: Var[LiteralAlign]

    # Additional offset along the alignment axis in pixels. Also accepts a function that returns the offset to read the dimensions of the popup. Defaults to 0.
    align_offset: Var[int]

    # Which side of the anchor element to align the popup against. May automatically change to avoid collisions. Defaults to bottom.
    side: Var[LiteralSide]

    # Distance between the anchor and the popup in pixels. Also accepts a function that returns the distance to read the dimensions of the popup. Defaults to 0.
    side_offset: Var[int]

    # Minimum distance to maintain between the arrow and the edges of the popup. Use it to prevent the arrow element from hanging out of the rounded corners of a popup. Defaults to 5.
    arrow_padding: Var[int]

    # An element to position the popup against. By default, the popup will be positioned against the trigger.
    anchor: Var[str]

    # An element or a rectangle that delimits the area that the popup is confined to. Defaults to clipping-ancestors.
    collision_boundary: Var[str]

    # Additional space to maintain from the edge of the collision boundary. Defaults to 5.
    collision_padding: Var[int | list[int]]

    # Whether to maintain the popup in the viewport after the anchor element was scrolled out of view. Defaults to false.
    sticky: Var[bool]

    # Determines which CSS position property to use. Defaults to absolute.
    position_method: Var[LiteralPosition]

    # Whether to disable the popup tracking any layout shift of its positioning anchor. Defaults to False.
    disable_anchor_tracking: Var[bool]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the preview card positioner component.

        Returns:
            The component.
        """
        props["data-slot"] = "preview-card-positioner"
        props.setdefault("side_offset", 8)
        cls.set_class_name(ClassNames.POSITIONER, props)
        return super().create(*children, **props)


class PreviewCardPopup(PreviewCardBaseComponent):
    """A container for the preview card contents. Renders a <div> element."""

    tag = "PreviewCard.Popup"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the preview card popup component.

        Returns:
            The component.
        """
        props["data-slot"] = "preview-card-popup"
        cls.set_class_name(ClassNames.POPUP, props)
        return super().create(*children, **props)


class PreviewCardArrow(PreviewCardBaseComponent):
    """Displays an element positioned against the preview card anchor. Renders a <div> element."""

    tag = "PreviewCard.Arrow"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the preview card arrow component.

        Returns:
            The component.
        """
        props["data-slot"] = "preview-card-arrow"
        cls.set_class_name(ClassNames.ARROW, props)
        return super().create(*children, **props)


class HighLevelPreviewCard(PreviewCardRoot):
    """High level wrapper for the PreviewCard component."""

    trigger: Var[Component | None]
    content: Var[str | Component | None]

    # Props for different component parts
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
        """Create a preview card component.

        Args:
            *children: Additional children to include in the preview card.
            **props: Additional properties to apply to the preview card component.

        Returns:
            The preview card component.
        """
        # Extract props for different parts
        positioner_props = {
            k: props.pop(k) for k in cls._positioner_props & props.keys()
        }
        portal_props = {k: props.pop(k) for k in cls._portal_props & props.keys()}

        trigger = props.pop("trigger", None)
        content = props.pop("content", None)
        class_name = props.pop("class_name", "")

        return PreviewCardRoot.create(
            PreviewCardTrigger.create(render_=trigger) if trigger is not None else None,
            PreviewCardPortal.create(
                PreviewCardPositioner.create(
                    PreviewCardPopup.create(
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
        ]


class PreviewCard(ComponentNamespace):
    """Namespace for PreviewCard components."""

    root = staticmethod(PreviewCardRoot.create)
    trigger = staticmethod(PreviewCardTrigger.create)
    backdrop = staticmethod(PreviewCardBackdrop.create)
    portal = staticmethod(PreviewCardPortal.create)
    positioner = staticmethod(PreviewCardPositioner.create)
    popup = staticmethod(PreviewCardPopup.create)
    arrow = staticmethod(PreviewCardArrow.create)
    class_names = ClassNames
    __call__ = staticmethod(HighLevelPreviewCard.create)


preview_card = PreviewCard()
