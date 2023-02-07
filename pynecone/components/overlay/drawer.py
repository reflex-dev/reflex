"""Container to stack elements with spacing."""

from typing import Set

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.components.media.icon import Icon
from pynecone.var import Var


class Drawer(ChakraComponent):
    """A drawer component."""

    tag = "Drawer"

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

    # If true and drawer's placement is top or bottom, the drawer will occupy the viewport height (100vh)
    is_full_height: Var[bool]

    # Enables aggressive focus capturing within iframes. - If true: keep focus in the lock, no matter where lock is active - If false: allows focus to move outside of iframe
    lock_focus_across_frames: Var[bool]

    # The placement of the drawer
    placement: Var[str]

    # If true, a `padding-right` will be applied to the body element that's equal to the width of the scrollbar. This can help prevent some unpleasant flickering effect and content adjustment when the modal opens
    preserve_scroll_bar_gap: Var[bool]

    # If true, the modal will return focus to the element that triggered it when it closes.
    return_focus_on_close: Var[bool]

    # "xs" | "sm" | "md" | "lg" | "xl" | "full"
    size: Var[str]

    # A11y: If true, the siblings of the modal will have `aria-hidden` set to true so that screen readers can only see the modal. This is commonly known as making the other elements **inert**
    use_inert: Var[bool]

    # Variant of drawer
    variant: Var[str]

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

    @classmethod
    def create(
        cls, *children, header=None, body=None, footer=None, close_button=None, **props
    ) -> Component:
        """Create a drawer component.

        Args:
            children: The children of the drawer component.
            header: The header of the drawer.
            body: The body of the drawer.
            footer: The footer of the drawer.
            close_button: The close button of the drawer.
            props: The properties of the drawer component.

        Raises:
            AttributeError: error that occurs if conflicting props are passed

        Returns:
            The drawer component.
        """
        if len(children) == 0:
            contents = []

            if header:
                contents.append(DrawerHeader.create(header))

            if body:
                contents.append(DrawerBody.create(body))

            if footer:
                contents.append(DrawerFooter.create(footer))

            if props.get("on_close"):
                # use default close button if undefined
                if not close_button:
                    close_button = Icon.create(tag="CloseIcon")
                contents.append(DrawerCloseButton.create(close_button))
            elif close_button:
                raise AttributeError(
                    "Close button can not be used if on_close event handler is not defined"
                )

            children = [
                DrawerOverlay.create(
                    DrawerContent.create(*contents),
                )
            ]

        return super().create(*children, **props)


class DrawerBody(ChakraComponent):
    """Drawer body."""

    tag = "DrawerBody"


class DrawerHeader(ChakraComponent):
    """Drawer header."""

    tag = "DrawerHeader"


class DrawerFooter(ChakraComponent):
    """Drawer footer."""

    tag = "DrawerFooter"


class DrawerOverlay(ChakraComponent):
    """Drawer overlay."""

    tag = "DrawerOverlay"


class DrawerContent(ChakraComponent):
    """Drawer content."""

    tag = "DrawerContent"


class DrawerCloseButton(ChakraComponent):
    """Drawer close button."""

    tag = "DrawerCloseButton"
