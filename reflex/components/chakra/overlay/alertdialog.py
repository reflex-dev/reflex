"""Alert dialog components."""

from __future__ import annotations

from reflex.components.chakra import ChakraComponent, LiteralAlertDialogSize
from reflex.components.chakra.media.icon import Icon
from reflex.components.component import Component
from reflex.event import EventHandler
from reflex.vars import Var


class AlertDialog(ChakraComponent):
    """Provides context and state for the dialog."""

    tag = "AlertDialog"

    # If true, the modal will be open.
    is_open: Var[bool]

    # The least destructive element to focus when the dialog opens.
    least_destructive_ref: Var[str]

    # Handle zoom/pinch gestures on iOS devices when scroll locking is enabled. Defaults to false.
    allow_pinch_zoom: Var[bool]

    # If true, the modal will autofocus the first enabled and interactive element within the ModalContent
    auto_focus: Var[bool]

    # If true, scrolling will be disabled on the body when the modal opens.
    block_scroll_on_mount: Var[bool]

    # If true, the modal will close when the Esc key is pressed
    close_on_esc: Var[bool]

    # If true, the modal will close when the overlay is clicked
    close_on_overlay_click: Var[bool]

    # If true, the modal will be centered on screen.
    is_centered: Var[bool]

    # Enables aggressive focus capturing within iframes. If true, keep focus in the lock, no matter where lock is active. If false, allows focus to move outside of iframe.
    lock_focus_across_frames: Var[bool]

    # If true, a `padding-right` will be applied to the body element that's equal to the width of the scrollbar. This can help prevent some unpleasant flickering effect and content adjustment when the modal opens
    preserve_scroll_bar_gap: Var[bool]

    # If true, the modal will return focus to the element that triggered it when it closes.
    return_focus_on_close: Var[bool]

    # "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl" | "5xl" | "6xl" | "full"
    size: Var[LiteralAlertDialogSize]

    # If true, the siblings of the modal will have `aria-hidden` set to true so that screen readers can only see the modal. This is commonly known as making the other elements **inert**
    use_inert: Var[bool]

    # Fired when the modal is closing.
    on_close: EventHandler[lambda: []]

    # Fired when the modal is closed and the exit animation is complete.
    on_close_complete: EventHandler[lambda: []]

    # Fired when the Esc key is pressed.
    on_esc: EventHandler[lambda: []]

    # Fired when the overlay is clicked.
    on_overlay_click: EventHandler[lambda: []]

    @classmethod
    def create(
        cls, *children, header=None, body=None, footer=None, close_button=None, **props
    ) -> Component:
        """Create an alert dialog component.

        Args:
            *children: The children of the alert dialog component.
            header: The header of the alert dialog.
            body: The body of the alert dialog.
            footer: The footer of the alert dialog.
            close_button: The close button of the alert dialog.
            **props: The properties of the alert dialog component.

        Raises:
            AttributeError: if there is a conflict between the props used.

        Returns:
            The alert dialog component.
        """
        if len(children) == 0:
            contents = []

            if header:
                contents.append(AlertDialogHeader.create(header))

            if body:
                contents.append(AlertDialogBody.create(body))

            if footer:
                contents.append(AlertDialogFooter.create(footer))

            # add AlertDialogCloseButton if either a prop for one was passed, or if on_close callback is present
            if props.get("on_close"):
                # get user defined close button or use default one
                if not close_button:
                    close_button = Icon.create(tag="close")
                contents.append(AlertDialogCloseButton.create(close_button))
            elif close_button:
                raise AttributeError(
                    "Close button can not be used if on_close event handler is not defined"
                )

            children = [
                AlertDialogOverlay.create(
                    AlertDialogContent.create(*contents),
                )
            ]

        return super().create(*children, **props)


class AlertDialogBody(ChakraComponent):
    """Should contain the description announced by screen readers."""

    tag = "AlertDialogBody"


class AlertDialogHeader(ChakraComponent):
    """Should contain the title announced by screen readers."""

    tag = "AlertDialogHeader"


class AlertDialogFooter(ChakraComponent):
    """Should contain the events of the dialog."""

    tag = "AlertDialogFooter"


class AlertDialogContent(ChakraComponent):
    """The wrapper for the alert dialog's content."""

    tag = "AlertDialogContent"


class AlertDialogOverlay(ChakraComponent):
    """The dimmed overlay behind the dialog."""

    tag = "AlertDialogOverlay"


class AlertDialogCloseButton(ChakraComponent):
    """The button that closes the dialog."""

    tag = "AlertDialogCloseButton"
