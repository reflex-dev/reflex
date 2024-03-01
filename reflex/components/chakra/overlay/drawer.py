"""Container to stack elements with spacing."""
from __future__ import annotations

from typing import Any, Optional, Union

from reflex.components.chakra import (
    ChakraComponent,
    LiteralColorScheme,
    LiteralDrawerSize,
)
from reflex.components.chakra.media.icon import Icon
from reflex.components.component import Component
from reflex.vars import Var


class Drawer(ChakraComponent):
    """A drawer component."""

    tag: str = "Drawer"

    # If true, the modal will be open.
    is_open: Optional[Var[bool]] = None

    # Handle zoom/pinch gestures on iOS devices when scroll locking is enabled. Defaults to false.
    allow_pinch_zoom: Optional[Var[bool]] = None

    # If true, the modal will autofocus the first enabled and interactive element within the ModalContent
    auto_focus: Optional[Var[bool]] = None

    # If true, scrolling will be disabled on the body when the modal opens.
    block_scroll_on_mount: Optional[Var[bool]] = None

    # If true, the modal will close when the Esc key is pressed
    close_on_esc: Optional[Var[bool]] = None

    # If true, the modal will close when the overlay is clicked
    close_on_overlay_click: Optional[Var[bool]] = None

    # If true, the modal will be centered on screen.
    is_centered: Optional[Var[bool]] = None

    # If true and drawer's placement is top or bottom, the drawer will occupy the viewport height (100vh)
    is_full_height: Optional[Var[bool]] = None

    # Enables aggressive focus capturing within iframes. - If true: keep focus in the lock, no matter where lock is active - If false: allows focus to move outside of iframe
    lock_focus_across_frames: Optional[Var[bool]] = None

    # The placement of the drawer
    placement: Optional[Var[str]] = None

    # If true, a `padding-right` will be applied to the body element that's equal to the width of the scrollbar. This can help prevent some unpleasant flickering effect and content adjustment when the modal opens
    preserve_scroll_bar_gap: Optional[Var[bool]] = None

    # If true, the modal will return focus to the element that triggered it when it closes.
    return_focus_on_close: Optional[Var[bool]] = None

    # "xs" | "sm" | "md" | "lg" | "xl" | "full"
    size: Optional[Var[LiteralDrawerSize]] = None

    # A11y: If true, the siblings of the modal will have `aria-hidden` set to true so that screen readers can only see the modal. This is commonly known as making the other elements **inert**
    use_inert: Optional[Var[bool]] = None

    # Variant of drawer
    variant: Optional[Var[str]] = None

    # Color scheme of the Drawer
    # Options:
    # "whiteAlpha" | "blackAlpha" | "gray" | "red" | "orange" | "yellow" | "green" | "teal" | "blue" | "cyan"
    # | "purple" | "pink" | "linkedin" | "facebook" | "messenger" | "whatsapp" | "twitter" | "telegram"
    color_scheme: Optional[Var[LiteralColorScheme]] = None

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
        cls, *children, header=None, body=None, footer=None, close_button=None, **props
    ) -> Component:
        """Create a drawer component.

        Args:
            *children: The children of the drawer component.
            header: The header of the drawer.
            body: The body of the drawer.
            footer: The footer of the drawer.
            close_button: The close button of the drawer.
            **props: The properties of the drawer component.

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
                    close_button = Icon.create(tag="close")
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

    tag: str = "DrawerBody"


class DrawerHeader(ChakraComponent):
    """Drawer header."""

    tag: str = "DrawerHeader"


class DrawerFooter(ChakraComponent):
    """Drawer footer."""

    tag: str = "DrawerFooter"


class DrawerOverlay(ChakraComponent):
    """Drawer overlay."""

    tag: str = "DrawerOverlay"


class DrawerContent(ChakraComponent):
    """Drawer content."""

    tag: str = "DrawerContent"


class DrawerCloseButton(ChakraComponent):
    """Drawer close button."""

    tag: str = "DrawerCloseButton"
