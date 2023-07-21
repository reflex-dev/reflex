"""Radix toast components."""
from typing import List, Literal, Optional

from reflex.components import Component


class ToastComponent(Component):
    """Base class for all toast components."""

    library = "@radix-ui/react-toast"

    is_default = False


class ToastProvider(ToastComponent):
    """Radix toast provider."""

    tag = "Provider"
    alias = "ToastProvider"

    duration: Optional[int]
    label: str
    swipe_direction: Optional[List[Literal["right", "left", "up", "down"]]]
    swipe_threshold: Optional[int]


class ToastViewport(ToastComponent):
    """Radix toast viewport."""

    tag = "Viewport"
    alias = "ToastViewport"

    as_child: Optional[bool]
    hotkey: Optional[List[str]]
    label: Optional[str]


class ToastRoot(ToastComponent):
    """Radix toast root component. Event handler props are not currently supported."""

    tag = "Root"
    alias = "ToastRoot"

    as_child: Optional[bool]
    type: Optional[Literal["foreground", "background"]]
    duration: Optional[int]
    default_open: Optional[bool]
    open: Optional[bool]
    force_mount: Optional[bool]


class ToastTitle(ToastComponent):
    """Radix toast title."""

    tag = "Title"
    alias = "ToastTitle"

    as_child: Optional[bool]


class ToastDescription(ToastComponent):
    """Radix toast description."""

    tag = "Description"
    alias = "ToastDescription"

    as_child: Optional[bool]


class ToastClose(ToastComponent):
    """Radix toast close."""

    tag = "Close"
    alias = "ToastClose"

    as_child: Optional[bool]


class ToastAction(ToastComponent):
    """Radix toast action."""

    tag = "Action"
    alias = "ToastAction"

    as_child: Optional[bool]
    alt_text: str
