"""Modal components."""
from __future__ import annotations

from typing import Any, Optional, Union

from reflex.components.component import Component
from reflex.components.libs.chakra import ChakraComponent
from reflex.components.media import Icon
from reflex.vars import Var


class Modal(ChakraComponent):
    """The wrapper that provides context for its children."""

    tag = "Modal"

    # If true, the modal will be open.
    is_open: Var[bool]

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

    # Enables aggressive focus capturing within iframes. - If true: keep focus in the lock, no matter where lock is active - If false: allows focus to move outside of iframe
    lock_focus_across_frames: Var[bool]

    # The transition that should be used for the modal
    motion_preset: Var[str]

    # If true, a `padding-right` will be applied to the body element that's equal to the width of the scrollbar. This can help prevent some unpleasant flickering effect and content adjustment when the modal opens
    preserve_scroll_bar_gap: Var[bool]

    # If true, the modal will return focus to the element that triggered it when it closes.
    return_focus_on_close: Var[bool]

    # "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl" | "5xl" | "6xl" | "full"
    size: Var[str]

    # A11y: If true, the siblings of the modal will have `aria-hidden` set to true so that screen readers can only see the modal. This is commonly known as making the other elements **inert**
    use_inert: Var[bool]

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_close": lambda: [],
            "on_close_complete": lambda: [],
            "on_esc": lambda: [],
            "on_overlay_click": lambda: [],
        }

    @classmethod
    def create(
        cls,
        *children,
        header: Optional[Union[Component, str]] = None,
        body: Optional[Union[Component, str]] = None,
        footer: Optional[Union[Component, str]] = None,
        close_button: Optional[Component] = None,
        **props,
    ) -> Component:
        """Create a modal component.

        Args:
            *children: The children of the component.
            header: The header of the modal.
            body: The body of the modal.
            footer: The footer of the modal.
            close_button: The close button of the modal.
            **props: The properties of the component.

        Raises:
            AttributeError: error that occurs if conflicting props are passed

        Returns:
            The modal component.
        """
        if len(children) == 0:
            contents = []

            # add header if present in props
            if header:
                contents.append(ModalHeader.create(header))

            # add ModalBody if present in props
            if body:
                contents.append(ModalBody.create(body))

            # add ModalFooter if present in props
            if footer:
                contents.append(ModalFooter.create(footer))

            # add ModalCloseButton if either a prop for one was passed, or if
            if props.get("on_close"):
                # get user defined close button or use default one
                if not close_button:
                    close_button = Icon.create(tag="close")
                contents.append(ModalCloseButton.create(close_button))
            elif close_button:
                raise AttributeError(
                    "Close button can not be used if on_close event handler is not defined"
                )

            children = [
                ModalOverlay.create(
                    ModalContent.create(*contents),
                )
            ]

        return super().create(*children, **props)


class ModalOverlay(ChakraComponent):
    """The dimmed overlay behind the modal dialog."""

    tag = "ModalOverlay"


class ModalHeader(ChakraComponent):
    """The header that labels the modal dialog."""

    tag = "ModalHeader"


class ModalFooter(ChakraComponent):
    """The footer that houses the modal events."""

    tag = "ModalFooter"


class ModalContent(ChakraComponent):
    """The container for the modal dialog's content."""

    tag = "ModalContent"


class ModalBody(ChakraComponent):
    """The wrapper that houses the modal's main content."""

    tag = "ModalBody"


class ModalCloseButton(ChakraComponent):
    """The button that closes the modal."""

    tag = "ModalCloseButton"
