"""Modal components."""

from typing import Set

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


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
    use_intert: Var[bool]

    @classmethod
    def get_triggers(cls) -> Set[str]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return super().get_triggers() | {
            "on_close",
            "on_close_complete",
            "on_esc",
            "on_overlay_click",
        }


class ModalOverlay(Modal):
    """The dimmed overlay behind the modal dialog."""

    tag = "ModalOverlay"


class ModalHeader(ChakraComponent):
    """The header that labels the modal dialog."""

    tag = "ModalHeader"


class ModalFooter(ChakraComponent):
    """The footer that houses the modal events."""

    tag = "ModalFooter"


class ModalContent(Modal):
    """The container for the modal dialog's content."""

    tag = "ModalContent"


class ModalBody(ChakraComponent):
    """The wrapper that houses the modal's main content."""

    tag = "ModalBody"


class ModalCloseButton(Modal):
    """The button that closes the modal."""

    tag = "ModalCloseButton"
