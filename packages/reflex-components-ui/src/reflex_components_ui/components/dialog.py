"""A dialog: a native modal ``dialog``, and what opens and closes it."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_ui.base import UIComponent
from reflex_components_ui.components._dialog import (
    DialogDescriptionBase,
    DialogRootBase,
    DialogSlot,
    DialogSurface,
    DialogTitleBase,
    DialogTriggerBase,
    surface,
)
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.dialog import DIALOG_CONTENT


class DialogRoot(DialogRootBase):
    """Root component for Dialog."""

    open: Var[bool] = field(doc="The controlled open state of the dialog.")

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the open state changes."
    )

    default_open: Var[bool] = field(
        doc="The open state of the dialog when it is initially rendered. Use when you do not need to control its open state."
    )


class DialogTrigger(DialogTriggerBase):
    """Trigger an action or event, to open a Dialog modal."""


class DialogTitle(DialogTitleBase):
    """Title component to display inside a Dialog modal."""


class DialogOverlay(DialogSurface):
    """The native dialog around the content of a Dialog modal."""

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the open state changes."
    )

    on_open_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the dialog is opened."
    )

    on_close_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the dialog is closed."
    )

    on_escape_key_down: EventHandler[no_args_event_spec] = field(
        doc="Fired when the escape key is pressed."
    )

    on_pointer_down_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer is down outside the dialog."
    )

    on_interact_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer interacts outside the dialog."
    )


_EVENTS = (
    "on_open_auto_focus",
    "on_close_auto_focus",
    "on_escape_key_down",
    "on_pointer_down_outside",
    "on_interact_outside",
)


class DialogContent(UIComponent, elements.Div):
    """Content component to display inside a Dialog modal."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = DIALOG_CONTENT

    size: Var[Responsive[Literal["1", "2", "3", "4"]]] = field(
        doc='DialogContent size "1" - "4"'
    )

    on_open_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the dialog is opened."
    )

    on_close_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the dialog is closed."
    )

    on_escape_key_down: EventHandler[no_args_event_spec] = field(
        doc="Fired when the escape key is pressed."
    )

    on_pointer_down_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer is down outside the dialog."
    )

    on_interact_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when the pointer interacts outside the dialog."
    )

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a DialogContent.

        Args:
            *children: What the dialog holds.
            **props: The properties of the component. Its styles are those
                of the panel, and its events those of the dialog around it.

        Returns:
            The native dialog, around the panel.
        """
        events = {event: props.pop(event) for event in _EVENTS if event in props}
        return surface(DialogOverlay, super().create(*children, **props), events)


class DialogDescription(DialogDescriptionBase):
    """Description component to display inside a Dialog modal."""


class DialogClose(DialogSlot):
    """Close button component to close an open Dialog modal."""


class Dialog(ComponentNamespace):
    """Dialog components namespace."""

    root = __call__ = staticmethod(DialogRoot.create)
    trigger = staticmethod(DialogTrigger.create)
    title = staticmethod(DialogTitle.create)
    content = staticmethod(DialogContent.create)
    description = staticmethod(DialogDescription.create)
    close = staticmethod(DialogClose.create)


dialog = Dialog()
