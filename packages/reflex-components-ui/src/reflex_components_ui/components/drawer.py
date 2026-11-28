"""A drawer: a native ``dialog`` whose panel slides in from an edge of the page."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.components.tags import CommonTag
from reflex_base.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex_base.vars.base import LiteralVar, Var
from reflex_components_core.base.fragment import Fragment

from reflex_components_ui.base import Part, UIComponent
from reflex_components_ui.components._dialog import (
    DialogPart,
    DialogRootBase,
    DialogSlot,
    DialogSurface,
)
from reflex_components_ui.components._group import choose, descendants, literal
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.drawer import (
    DRAWER,
    DRAWER_CONTENT,
    DRAWER_DESCRIPTION,
    DRAWER_HANDLE,
    DRAWER_OVERLAY,
    DRAWER_ROOT,
    DRAWER_TITLE,
)

LiteralDirectionType = Literal["top", "bottom", "left", "right"]

_AS_CHILD_DOC = "Change the default rendered element for the one passed as a child."


def _is_off(flag: Var | None) -> Var | bool:
    """Say whether a flag that is on unless it says otherwise is off.

    Args:
        flag: The flag, or None when it is left out.

    Returns:
        Whether it is off: a bool when it is known while compiling.
    """
    if flag is None:
        return False
    known = literal(flag)
    if not isinstance(known, Var):
        return known is False
    return Var(
        f"({known!s} === false)", _var_type=bool, _var_data=known._get_all_var_data()
    )


class DrawerRoot(DialogRootBase):
    """The Root component of a Drawer, contains all parts of a drawer."""

    styles: ClassVar[ComponentStyles] = DRAWER_ROOT

    as_child: Var[bool] = field(doc=_AS_CHILD_DOC)

    default_open: Var[bool] = field(
        doc="The open state of the drawer when it is initially rendered. Use when you do not need to control its open state."
    )

    open: Var[bool] = field(doc="Whether the drawer is open or not.")

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fires when the drawer is opened or closed."
    )

    modal: Var[bool] = field(
        doc="When `False`, it allows interaction with elements outside of the drawer without closing it. Defaults to `True`."
    )

    direction: Var[LiteralDirectionType] = field(
        doc='Direction of the drawer. This adjusts the animations and the drag direction. Defaults to `"bottom"`'
    )

    on_animation_end: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Gets triggered after the open or close animation ends, it receives an open argument with the open state of the drawer by the time the function was triggered."
    )

    dismissible: Var[bool] = field(
        doc="When `False`, dragging, clicking outside, pressing esc, etc. will not close the drawer. Use this in combination with the open prop, otherwise you won't be able to open/close the drawer."
    )

    handle_only: Var[bool] = field(
        doc="When `True`, dragging will only be possible by the handle."
    )

    snap_points: Sequence[str | float] | None = field(
        doc="Array of numbers from 0 to 100 that corresponds to % of the screen a given snap point should take up. Should go from least visible. Also Accept px values, which doesn't take screen height into account."
    )

    fade_from_index: Var[int] = field(
        doc="Index of a snapPoint from which the overlay fade should be applied. Defaults to the last snap point."
    )

    scroll_lock_timeout: Var[int] = field(
        doc="Duration for which the drawer is not draggable after scrolling content inside of the drawer. Defaults to 500ms"
    )

    prevent_scroll_restoration: Var[bool] = field(
        doc="When `True`, it prevents scroll restoration. Defaults to `True`."
    )

    should_scale_background: Var[bool] = field(
        doc="Enable background scaling, it requires container element with `vaul-drawer-wrapper` attribute to scale its background."
    )

    close_threshold: Var[float] = field(
        doc="Number between 0 and 1 that determines when the drawer should be closed."
    )

    def _post_init(self, *args, **kwargs):
        """Initialize the drawer, and give its parts what they share.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        super()._post_init(*args, **kwargs)
        # Rendered by the dialog, which knows when its panel has moved.
        on_animation_end = self.event_triggers.pop("on_animation_end", None)
        if on_animation_end is not None:
            for part in descendants(self, DrawerSurface, DialogRootBase):
                part._on_animation_end = on_animation_end

    def _exclude_props(self) -> list[str]:
        """Keep the props that are the ones of the drawer off the element.

        Returns:
            The props read as styles, and what the drawer hands its parts
            or does without: it is not dragged, so it has no snap points.
        """
        return [
            *super()._exclude_props(),
            "modal",
            "direction",
            "dismissible",
            "handle_only",
            "snap_points",
            "fade_from_index",
            "scroll_lock_timeout",
            "prevent_scroll_restoration",
            "should_scale_background",
            "close_threshold",
        ]


class DrawerPart(DialogPart):
    """A part of a drawer."""

    as_child: Var[bool] = field(doc=_AS_CHILD_DOC)


class DrawerTrigger(DialogSlot):
    """The button that opens the dialog."""

    as_child: Var[bool] = field(
        default=Var.create(True),
        doc="Defaults to true, if the first child acts as the trigger.",
    )

    # One declaration holds the styles of the trigger and of its child.
    _merges_slot: ClassVar[bool] = True

    _command: ClassVar[str] = "show-modal"

    _mark: ClassVar[str] = "data-rx-dialog-trigger"

    def _join(
        self,
        root: DialogRootBase,
        name: str,
        named: dict[str, Any],
        on_open_change: Any,
    ) -> None:
        """Take the id of the drawer the trigger opens.

        Args:
            root: The drawer the trigger is in.
            name: The id of the drawer.
            named: What names and describes the drawer, by the attribute.
            on_open_change: What the drawer does when it opens or closes.
        """
        super()._join(root, name, named, on_open_change)  # pyright: ignore[reportAttributeAccessIssue]
        if literal(getattr(root, "modal", None)) is not None:
            # A drawer that may not be modal is opened by its script alone.
            self._dialog = {}
        if self._command != "close":
            self._dialog["aria-controls"] = name

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the trigger.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag: its child, or a button around its children, with the
            state Radix gives what opens a dialog.
        """
        tag = super()._render(props)
        if not self._as_child:  # pyright: ignore[reportAttributeAccessIssue]
            tag = tag.add_props(type="button")
        if self._command == "close":
            return tag
        return tag.add_props(**{
            "aria-haspopup": "dialog",
            "aria-expanded": False,
            "data-state": "closed",
        })


class DrawerPortal(DrawerPart):
    """Portals your drawer into the body."""

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a DrawerPortal.

        Args:
            *children: What the drawer shows over the page.
            **props: The properties of the component.

        Returns:
            The children: a native dialog is over the page wherever it is.
        """
        return Fragment.create(*children)


class DrawerSurface(DialogSurface):
    """The native dialog around the content of a drawer."""

    styles: ClassVar[ComponentStyles] = DRAWER

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fires when the drawer is opened or closed."
    )

    on_open_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the drawer content is opened."
    )

    on_close_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the drawer content is closed."
    )

    on_escape_key_down: EventHandler[no_args_event_spec] = field(
        doc="Fired when the escape key is pressed."
    )

    on_pointer_down_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer is down outside the drawer content."
    )

    on_interact_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when interacting outside the drawer content."
    )

    def _post_init(self, *args, **kwargs):
        """Initialize the dialog, as the one of a drawer without props.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # What the style table reads as variants: the drawer sets them.
        self._direction: Any = None
        self._modal: Any = None
        self._on_animation_end: Any = None
        super()._post_init(*args, **kwargs)

    def _join(
        self,
        root: DialogRootBase,
        name: str,
        named: dict[str, Any],
        on_open_change: Any,
    ) -> None:
        """Take from a drawer where it comes from and how it is dismissed.

        Args:
            root: The drawer the dialog is in.
            name: The id of the drawer.
            named: What names and describes the drawer, by the attribute.
            on_open_change: What the drawer does when it opens or closes.
        """
        super()._join(root, name, named, on_open_change)  # pyright: ignore[reportAttributeAccessIssue]
        self._direction = getattr(root, "direction", None)
        modeless = _is_off(getattr(root, "modal", None))
        self._modal = choose(modeless, "false", "true")
        if modeless is not False:
            self._dialog["data-modal"] = choose(modeless, "false", None)  # pyright: ignore[reportAttributeAccessIssue]
        kept = _is_off(getattr(root, "dismissible", None))
        if kept is not False:
            self._dialog["data-rx-keep"] = choose(kept, "all", None)  # pyright: ignore[reportAttributeAccessIssue]
        for part in self.children:
            if isinstance(part, DrawerContent):
                part._direction = self._direction
                part._merge_styles()  # pyright: ignore[reportAttributeAccessIssue]
        self._merge_styles()  # pyright: ignore[reportAttributeAccessIssue]

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the dialog, what follows its panel included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        if self._on_animation_end is not None:
            yield LiteralVar.create(self._on_animation_end)

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the dialog.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, which says when its panel has slid in or out.
        """
        tag = super()._render(props)
        if self._on_animation_end is None:
            return tag
        handler = LiteralVar.create(self._on_animation_end)
        return tag.add_props(
            on_transition_end=Var(
                '((event) => event.propertyName === "transform" && '
                "event.target.parentElement === event.currentTarget && "
                f"({handler!s})(event.currentTarget.open))",
                _var_data=handler._get_all_var_data(),
            )
        )


_EVENTS = (
    "on_open_auto_focus",
    "on_close_auto_focus",
    "on_escape_key_down",
    "on_pointer_down_outside",
    "on_interact_outside",
)


# Based on https://www.radix-ui.com/primitives/docs/components/dialog#content
class DrawerContent(UIComponent):
    """Content that should be rendered in the drawer."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = DRAWER_CONTENT

    as_child: Var[bool] = field(doc=_AS_CHILD_DOC)

    on_open_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the drawer content is opened."
    )

    on_close_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the drawer content is closed."
    )

    on_escape_key_down: EventHandler[no_args_event_spec] = field(
        doc="Fired when the escape key is pressed."
    )

    on_pointer_down_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer is down outside the drawer content."
    )

    on_interact_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when interacting outside the drawer content."
    )

    @classmethod
    def create(cls, *children, **props):
        """Create a Drawer Content.

        Args:
            *children: The list of children to use.
            **props: Additional properties to apply to the drawer content.
                Its styles are those of the panel, and its events those of
                the dialog around it.

        Returns:
            The native dialog, around the panel.
        """
        events = {event: props.pop(event) for event in _EVENTS if event in props}
        return DrawerSurface.create(super().create(*children, **props), **events)

    def _post_init(self, *args, **kwargs):
        """Initialize the panel, as the one of a drawer without props.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # What the style table reads as a variant: the drawer sets it.
        self._direction: Any = None
        super()._post_init(*args, **kwargs)


class DrawerOverlay(DrawerPart):
    """A layer that covers the inert portion of the view when the dialog is open."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = DRAWER_OVERLAY

    def _post_init(self, *args, **kwargs):
        """Initialize the overlay, as the one of a modal drawer.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # What the style table reads as a variant: the drawer sets it.
        self._modal: Any = None
        super()._post_init(*args, **kwargs)

    def _join(
        self,
        root: DialogRootBase,
        name: str,
        named: dict[str, Any],
        on_open_change: Any,
    ) -> None:
        """Take from a drawer whether it is modal: only then has it an overlay.

        Args:
            root: The drawer the overlay is in.
            name: The id of the drawer.
            named: What names and describes the drawer, by the attribute.
            on_open_change: What the drawer does when it opens or closes.
        """
        self._modal = choose(_is_off(getattr(root, "modal", None)), "false", "true")
        self._merge_styles()  # pyright: ignore[reportAttributeAccessIssue]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the overlay.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, which stays until it has faded out.
        """
        return super()._render(props).add_props(**{"data-rx-popup": ""})


class DrawerClose(DrawerTrigger):
    """A button that closes the drawer."""

    _command: ClassVar[str] = "close"

    _mark: ClassVar[str] = "data-rx-dialog-close"


class DrawerTitle(DrawerPart):
    """A title for the drawer."""

    tag = "h2"

    styles: ClassVar[ComponentStyles] = DRAWER_TITLE

    _names: ClassVar[str | None] = "labelledby"


class DrawerDescription(DrawerPart):
    """A description for the drawer."""

    tag = "p"

    styles: ClassVar[ComponentStyles] = DRAWER_DESCRIPTION

    _names: ClassVar[str | None] = "describedby"


class DrawerHandle(DrawerPart):
    """A description for the drawer."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = DRAWER_HANDLE

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a DrawerHandle.

        Args:
            *children: What the handle holds.
            **props: The properties of the component.

        Returns:
            The handle: a bar, with room around it for a finger.
        """
        return super().create(
            Part.create(
                *children,
                part="hitarea",
                tag="span",
                custom_attrs={"aria-hidden": True},
            ),
            **props,
        )

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the handle.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, which is nothing to assistive technology.
        """
        return super()._render(props).add_props(**{"aria-hidden": True})


class Drawer(ComponentNamespace):
    """A namespace for Drawer components."""

    root = __call__ = staticmethod(DrawerRoot.create)
    trigger = staticmethod(DrawerTrigger.create)
    portal = staticmethod(DrawerPortal.create)
    content = staticmethod(DrawerContent.create)
    overlay = staticmethod(DrawerOverlay.create)
    close = staticmethod(DrawerClose.create)
    title = staticmethod(DrawerTitle.create)
    description = staticmethod(DrawerDescription.create)
    handle = staticmethod(DrawerHandle.create)


drawer = Drawer()
