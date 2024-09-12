"""Drawer components based on Radix primitives."""

# Based on Vaul: https://github.com/emilkowalski/vaul
# Style based on https://ui.shadcn.com/docs/components/drawer
from __future__ import annotations

from typing import Any, List, Literal, Optional, Union

from reflex.components.component import Component, ComponentNamespace
from reflex.components.radix.primitives.base import RadixPrimitiveComponent
from reflex.components.radix.themes.base import Theme
from reflex.components.radix.themes.layout.flex import Flex
from reflex.event import EventHandler
from reflex.vars.base import Var


class DrawerComponent(RadixPrimitiveComponent):
    """A Drawer component."""

    library = "vaul"

    lib_dependencies: List[str] = ["@radix-ui/react-dialog@^1.0.5"]


LiteralDirectionType = Literal["top", "bottom", "left", "right"]


class DrawerRoot(DrawerComponent):
    """The Root component of a Drawer, contains all parts of a drawer."""

    tag = "Drawer.Root"

    alias = "Vaul" + tag

    # Whether the drawer is open or not.
    open: Var[bool]

    # Enable background scaling, it requires an element with [vaul-drawer-wrapper] data attribute to scale its background.
    should_scale_background: Var[bool]

    # Number between 0 and 1 that determines when the drawer should be closed.
    close_threshold: Var[float]

    # Array of numbers from 0 to 100 that corresponds to % of the screen a given snap point should take up. Should go from least visible. Also Accept px values, which doesn't take screen height into account.
    snap_points: Optional[List[Union[str, float]]]

    # Index of a snapPoint from which the overlay fade should be applied. Defaults to the last snap point.
    fade_from_index: Var[int]

    # Duration for which the drawer is not draggable after scrolling content inside of the drawer. Defaults to 500ms
    scroll_lock_timeout: Var[int]

    # When `False`, it allows to interact with elements outside of the drawer without closing it. Defaults to `True`.
    modal: Var[bool]

    # Direction of the drawer. Defaults to `"bottom"`
    direction: Var[LiteralDirectionType]

    # When `True`, it prevents scroll restoration. Defaults to `True`.
    preventScrollRestoration: Var[bool]

    # Fires when the drawer is opened.
    on_open_change: EventHandler[lambda e0: [e0]]


class DrawerTrigger(DrawerComponent):
    """The button that opens the dialog."""

    tag = "Drawer.Trigger"

    alias = "Vaul" + tag

    # Defaults to true, if the first child acts as the trigger.
    as_child: Var[bool] = True  # type: ignore

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a new DrawerTrigger instance.

        Args:
            children: The children of the element.
            props: The properties of the element.

        Returns:
            The new DrawerTrigger instance.
        """
        for child in children:
            if "on_click" in getattr(child, "event_triggers", {}):
                children = (Flex.create(*children),)
                break
        return super().create(*children, **props)


class DrawerPortal(DrawerComponent):
    """Portals your drawer into the body."""

    tag = "Drawer.Portal"

    alias = "Vaul" + tag


# Based on https://www.radix-ui.com/primitives/docs/components/dialog#content
class DrawerContent(DrawerComponent):
    """Content that should be rendered in the drawer."""

    tag = "Drawer.Content"

    alias = "Vaul" + tag

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
        return {"css": base_style}

    # Fired when the drawer content is opened.
    on_open_auto_focus: EventHandler[lambda e0: [e0.target.value]]

    # Fired when the drawer content is closed.
    on_close_auto_focus: EventHandler[lambda e0: [e0.target.value]]

    # Fired when the escape key is pressed.
    on_escape_key_down: EventHandler[lambda e0: [e0.target.value]]

    # Fired when the pointer is down outside the drawer content.
    on_pointer_down_outside: EventHandler[lambda e0: [e0.target.value]]

    # Fired when interacting outside the drawer content.
    on_interact_outside: EventHandler[lambda e0: [e0.target.value]]

    @classmethod
    def create(cls, *children, **props):
        """Create a Drawer Content.
         We wrap the Drawer content in an `rx.theme` to make radix themes definitions available to
         rendered div in the DOM. This is because Vaul Drawer injects the Drawer overlay content in a sibling
         div to the root div rendered by radix which contains styling definitions. Wrapping in `rx.theme`
         makes the styling available to the overlay.

        Args:
            *children: The list of children to use.
            **props: Additional properties to apply to the drawer content.

        Returns:
                 The drawer content.
        """
        comp = super().create(*children, **props)

        return Theme.create(comp)


class DrawerOverlay(DrawerComponent):
    """A layer that covers the inert portion of the view when the dialog is open."""

    tag = "Drawer.Overlay"

    alias = "Vaul" + tag

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
            "background": "rgba(0, 0, 0, 0.5)",
        }
        style = self.style or {}
        base_style.update(style)
        return {"css": base_style}


class DrawerClose(DrawerTrigger):
    """A button that closes the drawer."""

    tag = "Drawer.Close"

    alias = "Vaul" + tag


class DrawerTitle(DrawerComponent):
    """A title for the drawer."""

    tag = "Drawer.Title"

    alias = "Vaul" + tag

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
        return {"css": base_style}


class DrawerDescription(DrawerComponent):
    """A description for the drawer."""

    tag = "Drawer.Description"

    alias = "Vaul" + tag

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
        return {"css": base_style}


class Drawer(ComponentNamespace):
    """A namespace for Drawer components."""

    root = __call__ = staticmethod(DrawerRoot.create)
    trigger = staticmethod(DrawerTrigger.create)
    portal = staticmethod(DrawerPortal.create)
    content = staticmethod(DrawerContent.create)
    overlay = staticmethod(DrawerOverlay.create)
    close = staticmethod(DrawerClose.create)
    title = staticmethod(DrawerTitle.create)
    description = staticmethod(DrawerDescription.create)


drawer = Drawer()
