"""An alert dialog: a native modal ``dialog`` that waits for an answer."""

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

LiteralContentSize = Literal["1", "2", "3", "4"]


class AlertDialogRoot(DialogRootBase):
    """Contains all the parts of the dialog."""

    open: Var[bool] = field(doc="The controlled open state of the dialog.")

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the open state changes."
    )

    default_open: Var[bool] = field(
        doc="The open state of the dialog when it is initially rendered. Use when you do not need to control its open state."
    )


class AlertDialogTrigger(DialogTriggerBase):
    """Wraps the control that will open the dialog."""


class AlertDialogOverlay(DialogSurface):
    """The native dialog around the content of an alert dialog."""

    # A press beside the panel of an alert dialog does not dismiss it.
    _role: ClassVar[str | None] = "alertdialog"

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


_EVENTS = ("on_open_auto_focus", "on_close_auto_focus", "on_escape_key_down")


class AlertDialogContent(UIComponent, elements.Div):
    """Contains the content of the dialog. This component is based on the div element."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = DIALOG_CONTENT

    size: Var[Responsive[LiteralContentSize]] = field(doc="The size of the content.")

    force_mount: Var[bool] = field(doc="Whether to force mount the content on open.")

    on_open_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the dialog is opened."
    )

    on_close_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the dialog is closed."
    )

    on_escape_key_down: EventHandler[no_args_event_spec] = field(
        doc="Fired when the escape key is pressed."
    )

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create an AlertDialogContent.

        Args:
            *children: What the dialog holds.
            **props: The properties of the component. Its styles are those
                of the panel, and its events those of the dialog around it.

        Returns:
            The native dialog, around the panel.
        """
        events = {event: props.pop(event) for event in _EVENTS if event in props}
        return surface(AlertDialogOverlay, super().create(*children, **props), events)

    def _exclude_props(self) -> list[str]:
        """Keep the prop that is no attribute off the element.

        Returns:
            The props read as styles, and whether the content stays
            mounted: it always is.
        """
        return [*super()._exclude_props(), "force_mount"]


class AlertDialogTitle(DialogTitleBase):
    """An accessible title that is announced when the dialog is opened.
    This part is based on the Heading component with a pre-defined font size and
    leading trim on top.
    """


class AlertDialogDescription(DialogDescriptionBase):
    """An optional accessible description that is announced when the dialog is opened.
    This part is based on the Text component with a pre-defined font size.
    """


class AlertDialogAction(DialogSlot):
    """Wraps the control that will close the dialog. This should be distinguished
    visually from the Cancel control.
    """


class AlertDialogCancel(DialogSlot):
    """Wraps the control that will close the dialog. This should be distinguished
    visually from the Action control.
    """

    # The dialog gives the focus to what cancels it when it opens.
    _marked: ClassVar[str] = "cancel"


class AlertDialog(ComponentNamespace):
    """AlertDialog components namespace."""

    root = staticmethod(AlertDialogRoot.create)
    trigger = staticmethod(AlertDialogTrigger.create)
    content = staticmethod(AlertDialogContent.create)
    title = staticmethod(AlertDialogTitle.create)
    description = staticmethod(AlertDialogDescription.create)
    action = staticmethod(AlertDialogAction.create)
    cancel = staticmethod(AlertDialogCancel.create)


alert_dialog = AlertDialog()
