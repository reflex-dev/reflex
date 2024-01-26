"""Drawer components based on Radix primitives."""
# Based on Vaul: https://github.com/emilkowalski/vaul
# Style based on https://ui.shadcn.com/docs/components/drawer
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from reflex.components.radix.primitives.base import RadixPrimitiveComponentWithClassName
from reflex.constants import EventTriggers
from reflex.vars import Var


class DrawerComponent(RadixPrimitiveComponentWithClassName):
    """A Drawer component."""

    library = "vaul"

    lib_dependencies: List[str] = ["@radix-ui/react-dialog@^1.0.5"]


LiteralDirectionType = Literal[
    "top",
    "bottom",
    "left",
    "right",
]


class DrawerRoot(DrawerComponent):
    """The Root component of a Drawer, contains all parts of a drawer."""

    tag = "Drawer.Root"

    # Whether the drawer is open or not.
    open: Var[bool]

    # Enable background scaling,
    # it requires an element with [vaul-drawer-wrapper] data attribute to scale its background.
    should_scale_background: Var[bool]

    # Number between 0 and 1 that determines when the drawer should be closed.
    close_threshold: Var[float]

    # Array of numbers from 0 to 100 that corresponds to % of the screen a given snap point should take up. Should go from least visible.
    # Also Accept px values, which doesn't take screen height into account.
    snap_points: Optional[List[Union[str, float]]]

    # Index of a snapPoint from which the overlay fade should be applied.
    # Defaults to the last snap point.
    # TODO: will it accept -1 then?
    fade_from_index: Var[int]

    # Duration for which the drawer is not draggable after scrolling content inside of the drawer. Defaults to 500ms
    scroll_lock_timeout: Var[int]

    # When `False`, it allows to interact with elements outside of the drawer without closing it.
    # Defaults to `True`.
    modal: Var[bool]

    # Direction of the drawer. Defaults to `"bottom"`
    direction: Var[LiteralDirectionType]

    # When `True`, it prevents scroll restoration
    # when the drawer is closed after a navigation happens inside of it.
    # Defaults to `True`.
    preventScrollRestoration: Var[bool]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_OPEN_CHANGE: lambda e0: [e0.target.value],
        }


class DrawerTrigger(DrawerComponent):
    """The button that opens the dialog."""

    tag = "Drawer.Trigger"

    as_child: Var[bool]


class DrawerPortal(DrawerComponent):
    """Portals your drawer into the body."""

    tag = "Drawer.Portal"


# Based on https://www.radix-ui.com/primitives/docs/components/dialog#content
class DrawerContent(DrawerComponent):
    """Content that should be rendered in the drawer."""

    tag = "Drawer.Content"

    # Style set partially based on the source code at https://ui.shadcn.com/docs/components/drawer
    def _get_style(self) -> dict:
        """Get the style for the component.

        Returns:
            The dictionary of the component style as value and the style notation as key.
        """
        base_style = {
            "left": "0",
            "right": "0",
            "bottom": "0",
            "top": "0",
            "position": "fixed",
            "z_index": 50,
            "display": "flex",
        }
        style = self.style or {}
        base_style.update(style)
        self.style.update(
            {
                "css": base_style,
            }
        )
        return self.style

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            # DrawerContent is based on Radix DialogContent
            # These are the same triggers as DialogContent
            EventTriggers.ON_OPEN_AUTO_FOCUS: lambda e0: [e0.target.value],
            EventTriggers.ON_CLOSE_AUTO_FOCUS: lambda e0: [e0.target.value],
            EventTriggers.ON_ESCAPE_KEY_DOWN: lambda e0: [e0.target.value],
            EventTriggers.ON_POINTER_DOWN_OUTSIDE: lambda e0: [e0.target.value],
            EventTriggers.ON_INTERACT_OUTSIDE: lambda e0: [e0.target.value],
        }


class DrawerOverlay(DrawerComponent):
    """A layer that covers the inert portion of the view when the dialog is open."""

    tag = "Drawer.Overlay"

    # Style set based on the source code at https://ui.shadcn.com/docs/components/drawer
    def _get_style(self) -> dict:
        """Get the style for the component.

        Returns:
            The dictionary of the component style as value and the style notation as key.
        """
        base_style = {
            "position": "fixed",
            "left": "0",
            "right": "0",
            "bottom": "0",
            "top": "0",
            "z_index": 50,
            "background": "rgba(0, 0, 0, 0.8)",
        }
        style = self.style or {}
        base_style.update(style)
        self.style.update(
            {
                "css": base_style,
            }
        )
        return self.style


class DrawerClose(DrawerComponent):
    """A button that closes the drawer."""

    tag = "Drawer.Close"


class DrawerTitle(DrawerComponent):
    """A title for the drawer."""

    tag = "Drawer.Title"

    # Style set based on the source code at https://ui.shadcn.com/docs/components/drawer
    def _get_style(self) -> dict:
        """Get the style for the component.

        Returns:
            The dictionary of the component style as value and the style notation as key.
        """
        base_style = {
            "font-size": "1.125rem",
            "font-weight": "600",
            "line-weight": "1",
            "letter-spacing": "-0.05em",
        }
        style = self.style or {}
        base_style.update(style)
        self.style.update(
            {
                "css": base_style,
            }
        )
        return self.style


class DrawerDescription(DrawerComponent):
    """A description for the drawer."""

    tag = "Drawer.Description"

    # Style set based on the source code at https://ui.shadcn.com/docs/components/drawer
    def _get_style(self) -> dict:
        """Get the style for the component.

        Returns:
            The dictionary of the component style as value and the style notation as key.
        """
        base_style = {
            "font-size": "0.875rem",
        }
        style = self.style or {}
        base_style.update(style)
        self.style.update(
            {
                "css": base_style,
            }
        )
        return self.style


drawer_root = DrawerRoot.create
drawer_trigger = DrawerTrigger.create
drawer_portal = DrawerPortal.create
drawer_content = DrawerContent.create
drawer_overlay = DrawerOverlay.create
drawer_close = DrawerClose.create
drawer_title = DrawerTitle.create
drawer_description = DrawerDescription.create
