"""Interactive components provided by @radix-ui/react-dialog."""

from typing import Any, ClassVar

from reflex.components.component import ComponentNamespace
from reflex.components.el import elements
from reflex.constants.compiler import MemoizationMode
from reflex.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex.vars.base import Var

from .base import RadixPrimitiveComponent, RadixPrimitiveTriggerComponent


class DialogElement(RadixPrimitiveComponent):
    """Base class for all @radix-ui/react-dialog components."""

    library = "@radix-ui/react-dialog@1.1.15"


class DialogRoot(DialogElement):
    """Root component for Dialog."""

    tag = "Root"
    alias = "RadixPrimitiveDialogRoot"

    # The controlled open state of the dialog.
    open: Var[bool]

    # Fired when the open state changes.
    on_open_change: EventHandler[passthrough_event_spec(bool)]

    # The open state of the dialog when it is initially rendered. Use when you do not need to control its open state.
    default_open: Var[bool]

    # The modality of the dialog. When set to true, interaction with outside elements will be disabled and only dialog content will be visible to screen readers.
    modal: Var[bool]

    _valid_children: ClassVar[list[str]] = [
        "DialogTrigger",
        "DialogPortal",
    ]


class DialogPortal(DialogElement):
    """Portal component for Dialog."""

    tag = "Portal"
    alias = "RadixPrimitiveDialogPortal"

    # Used to force mounting when more control is needed. Useful when controlling animation with React animation libraries. If used on this part, it will be inherited by Dialog.Overlay and Dialog.Content.
    force_mount: Var[bool]

    # Specify a container element to portal the content into.
    container: Var[Any]

    _valid_parents: ClassVar[list[str]] = ["DialogRoot"]


class DialogOverlay(DialogElement):
    """A layer that covers the inert portion of the view when the dialog is open."""

    tag = "Overlay"
    alias = "RadixPrimitiveDialogOverlay"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Used to force mounting when more control is needed. Useful when controlling animation with React animation libraries. It inherits from Dialog.Portal.
    force_mount: Var[bool]

    _valid_parents: ClassVar[list[str]] = ["DialogPortal"]


class DialogTrigger(DialogElement, RadixPrimitiveTriggerComponent):
    """Trigger an action or event, to open a Dialog modal."""

    tag = "Trigger"
    alias = "RadixPrimitiveDialogTrigger"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    _memoization_mode = MemoizationMode(recursive=False)

    _valid_parents: ClassVar[list[str]] = ["DialogRoot"]


class DialogContent(elements.Div, DialogElement):
    """Content component to display inside a Dialog modal."""

    tag = "Content"
    alias = "RadixPrimitiveDialogContent"

    # Used to force mounting when more control is needed. Useful when controlling animation with React animation libraries. It inherits from Dialog.Portal.
    force_mount: Var[bool]

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Fired when the dialog is opened.
    on_open_auto_focus: EventHandler[no_args_event_spec]

    # Fired when the dialog is closed.
    on_close_auto_focus: EventHandler[no_args_event_spec]

    # Fired when the escape key is pressed.
    on_escape_key_down: EventHandler[no_args_event_spec]

    # Fired when the pointer is down outside the dialog.
    on_pointer_down_outside: EventHandler[no_args_event_spec]

    # Fired when the pointer interacts outside the dialog.
    on_interact_outside: EventHandler[no_args_event_spec]

    _valid_parents: ClassVar[list[str]] = ["DialogPortal"]


class DialogTitle(DialogElement):
    """Title component to display inside a Dialog modal."""

    tag = "Title"
    alias = "RadixPrimitiveDialogTitle"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]


class DialogDescription(DialogElement):
    """Description component to display inside a Dialog modal."""

    tag = "Description"
    alias = "RadixPrimitiveDialogDescription"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]


class DialogClose(DialogElement, RadixPrimitiveTriggerComponent):
    """Close button component to close an open Dialog modal."""

    tag = "Close"
    alias = "RadixPrimitiveDialogClose"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]


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
