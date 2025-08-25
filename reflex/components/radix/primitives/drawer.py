"""Drawer components based on Radix primitives."""

# Based on Vaul: https://github.com/emilkowalski/vaul
# Style based on https://ui.shadcn.com/docs/components/drawer
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from reflex.components.component import Component, ComponentNamespace
from reflex.components.radix.primitives.base import RadixPrimitiveComponent
from reflex.components.radix.themes.base import Theme
from reflex.components.radix.themes.layout.flex import Flex
from reflex.constants.compiler import MemoizationMode
from reflex.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex.vars.base import Var


class DrawerComponent(RadixPrimitiveComponent):
    """A Drawer component."""

    library = "vaul@1.1.2"

    lib_dependencies: list[str] = ["@radix-ui/react-dialog@1.1.15"]


LiteralDirectionType = Literal["top", "bottom", "left", "right"]


class DrawerRoot(DrawerComponent):
    """The Root component of a Drawer, contains all parts of a drawer."""

    tag = "Drawer.Root"

    alias = "Vaul" + tag

    # The open state of the drawer when it is initially rendered. Use when you do not need to control its open state.
    default_open: Var[bool]

    # Whether the drawer is open or not.
    open: Var[bool]

    # Fires when the drawer is opened or closed.
    on_open_change: EventHandler[passthrough_event_spec(bool)]

    # When `False`, it allows interaction with elements outside of the drawer without closing it. Defaults to `True`.
    modal: Var[bool]

    # Direction of the drawer. This adjusts the animations and the drag direction. Defaults to `"bottom"`
    direction: Var[LiteralDirectionType]

    # Gets triggered after the open or close animation ends, it receives an open argument with the open state of the drawer by the time the function was triggered.
    on_animation_end: EventHandler[passthrough_event_spec(bool)]

    # When `False`, dragging, clicking outside, pressing esc, etc. will not close the drawer. Use this in combination with the open prop, otherwise you won't be able to open/close the drawer.
    dismissible: Var[bool]

    # When `True`, dragging will only be possible by the handle.
    handle_only: Var[bool]

    # Array of numbers from 0 to 100 that corresponds to % of the screen a given snap point should take up. Should go from least visible. Also Accept px values, which doesn't take screen height into account.
    snap_points: Sequence[str | float] | None

    # Index of a snapPoint from which the overlay fade should be applied. Defaults to the last snap point.
    fade_from_index: Var[int]

    # Duration for which the drawer is not draggable after scrolling content inside of the drawer. Defaults to 500ms
    scroll_lock_timeout: Var[int]

    # When `True`, it prevents scroll restoration. Defaults to `True`.
    prevent_scroll_restoration: Var[bool]

    # Enable background scaling, it requires container element with `vaul-drawer-wrapper` attribute to scale its background.
    should_scale_background: Var[bool]

    # Number between 0 and 1 that determines when the drawer should be closed.
    close_threshold: Var[float]


class DrawerTrigger(DrawerComponent):
    """The button that opens the dialog."""

    tag = "Drawer.Trigger"

    alias = "Vaul" + tag

    # Defaults to true, if the first child acts as the trigger.
    as_child: Var[bool] = Var.create(True)

    _memoization_mode = MemoizationMode(recursive=False)

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a new DrawerTrigger instance.

        Args:
            *children: The children of the element.
            **props: The properties of the element.

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
    def add_style(self) -> dict:
        """Get the style for the component.

        Returns:
            The dictionary of the component style as value and the style notation as key.
        """
        return {
            "left": "0",
            "right": "0",
            "bottom": "0",
            "top": "0",
            "position": "fixed",
            "z_index": 50,
            "display": "flex",
        }

    # Fired when the drawer content is opened.
    on_open_auto_focus: EventHandler[no_args_event_spec]

    # Fired when the drawer content is closed.
    on_close_auto_focus: EventHandler[no_args_event_spec]

    # Fired when the escape key is pressed.
    on_escape_key_down: EventHandler[no_args_event_spec]

    # Fired when the pointer is down outside the drawer content.
    on_pointer_down_outside: EventHandler[no_args_event_spec]

    # Fired when interacting outside the drawer content.
    on_interact_outside: EventHandler[no_args_event_spec]

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
    def add_style(self) -> dict:
        """Get the style for the component.

        Returns:
            The dictionary of the component style as value and the style notation as key.
        """
        return {
            "position": "fixed",
            "left": "0",
            "right": "0",
            "bottom": "0",
            "top": "0",
            "z_index": 50,
            "background": "rgba(0, 0, 0, 0.5)",
        }


class DrawerClose(DrawerTrigger):
    """A button that closes the drawer."""

    tag = "Drawer.Close"

    alias = "Vaul" + tag


class DrawerTitle(DrawerComponent):
    """A title for the drawer."""

    tag = "Drawer.Title"

    alias = "Vaul" + tag

    # Style set based on the source code at https://ui.shadcn.com/docs/components/drawer
    def add_style(self) -> dict:
        """Get the style for the component.

        Returns:
            The dictionary of the component style as value and the style notation as key.
        """
        return {
            "font-size": "1.125rem",
            "font-weight": "600",
            "line-height": "1",
            "letter-spacing": "-0.05em",
        }


class DrawerDescription(DrawerComponent):
    """A description for the drawer."""

    tag = "Drawer.Description"

    alias = "Vaul" + tag

    # Style set based on the source code at https://ui.shadcn.com/docs/components/drawer
    def add_style(self) -> dict:
        """Get the style for the component.

        Returns:
            The dictionary of the component style as value and the style notation as key.
        """
        return {
            "font-size": "0.875rem",
        }


class DrawerHandle(DrawerComponent):
    """A description for the drawer."""

    tag = "Drawer.Handle"

    alias = "Vaul" + tag


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
    handle = staticmethod(DrawerHandle.create)


drawer = Drawer()
