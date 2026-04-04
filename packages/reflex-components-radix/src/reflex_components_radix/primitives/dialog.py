"""Interactive components provided by @radix-ui/react-dialog."""

from typing import Any, ClassVar

from reflex_base.components.component import ComponentNamespace, field
from reflex_base.constants.compiler import MemoizationMode
from reflex_base.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.el import elements

from .base import RadixPrimitiveComponent, RadixPrimitiveTriggerComponent


class DialogElement(RadixPrimitiveComponent):
    """Base class for all @radix-ui/react-dialog components."""

    library = "@radix-ui/react-dialog@1.1.15"


class DialogRoot(DialogElement):
    """Root component for Dialog."""

    tag = "Root"
    alias = "RadixPrimitiveDialogRoot"

    open: Var[bool] = field(doc="The controlled open state of the dialog.")

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the open state changes."
    )

    default_open: Var[bool] = field(
        doc="The open state of the dialog when it is initially rendered. Use when you do not need to control its open state."
    )

    modal: Var[bool] = field(
        doc="The modality of the dialog. When set to true, interaction with outside elements will be disabled and only dialog content will be visible to screen readers."
    )

    _valid_children: ClassVar[list[str]] = [
        "DialogTrigger",
        "DialogPortal",
    ]


class DialogPortal(DialogElement):
    """Portal component for Dialog."""

    tag = "Portal"
    alias = "RadixPrimitiveDialogPortal"

    force_mount: Var[bool] = field(
        doc="Used to force mounting when more control is needed. Useful when controlling animation with React animation libraries. If used on this part, it will be inherited by Dialog.Overlay and Dialog.Content."
    )

    container: Var[Any] = field(
        doc="Specify a container element to portal the content into."
    )

    _valid_parents: ClassVar[list[str]] = ["DialogRoot"]


class DialogOverlay(DialogElement):
    """A layer that covers the inert portion of the view when the dialog is open."""

    tag = "Overlay"
    alias = "RadixPrimitiveDialogOverlay"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    force_mount: Var[bool] = field(
        doc="Used to force mounting when more control is needed. Useful when controlling animation with React animation libraries. It inherits from Dialog.Portal."
    )

    _valid_parents: ClassVar[list[str]] = ["DialogPortal"]


class DialogTrigger(DialogElement, RadixPrimitiveTriggerComponent):
    """Trigger an action or event, to open a Dialog modal."""

    tag = "Trigger"
    alias = "RadixPrimitiveDialogTrigger"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    _memoization_mode = MemoizationMode(recursive=False)

    _valid_parents: ClassVar[list[str]] = ["DialogRoot"]


class DialogContent(elements.Div, DialogElement):
    """Content component to display inside a Dialog modal."""

    tag = "Content"
    alias = "RadixPrimitiveDialogContent"

    force_mount: Var[bool] = field(
        doc="Used to force mounting when more control is needed. Useful when controlling animation with React animation libraries. It inherits from Dialog.Portal."
    )

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
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

    _valid_parents: ClassVar[list[str]] = ["DialogPortal"]


class DialogTitle(DialogElement):
    """Title component to display inside a Dialog modal."""

    tag = "Title"
    alias = "RadixPrimitiveDialogTitle"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )


class DialogDescription(DialogElement):
    """Description component to display inside a Dialog modal."""

    tag = "Description"
    alias = "RadixPrimitiveDialogDescription"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )


class DialogClose(DialogElement, RadixPrimitiveTriggerComponent):
    """Close button component to close an open Dialog modal."""

    tag = "Close"
    alias = "RadixPrimitiveDialogClose"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )


class Dialog(ComponentNamespace):
    """Dialog components namespace."""

    root = __call__ = staticmethod(DialogRoot.create)
    portal = staticmethod(DialogPortal.create)
    trigger = staticmethod(DialogTrigger.create)
    title = staticmethod(DialogTitle.create)
    overlay = staticmethod(DialogOverlay.create)
    content = staticmethod(DialogContent.create)
    description = staticmethod(DialogDescription.create)
    close = staticmethod(DialogClose.create)


dialog = Dialog()
