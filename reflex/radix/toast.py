"""Radix toast components."""
from typing import List, Literal

from reflex.components import Component
from reflex.vars import Var


class ToastComponent(Component):
    """Base class for all toast components."""

    library = "@radix-ui/react-toast"
    is_default = False


class ToastProvider(ToastComponent):
    """Radix toast provider."""

    tag = "Provider"
    alias = "ToastProvider"

    duration: Var[int]
    label: Var[str]
    swipe_direction: Var[List[Literal["right", "left", "up", "down"]]]
    swipe_threshold: Var[int]


class ToastViewport(ToastComponent):
    """Radix toast viewport."""

    tag = "Viewport"
    alias = "ToastViewport"

    as_child: Var[bool]
    hotkey: Var[List[str]]
    label: Var[str]


class ToastRoot(ToastComponent):
    """Radix toast root component. Event handler props are not currently supported."""

    tag = "Root"
    alias = "ToastRoot"

    as_child: Var[bool]
    type_: Var[Literal["foreground", "background"]]
    duration: Var[int]
    default_open: Var[bool]
    open: Var[bool]
    force_mount: Var[bool]


class ToastTitle(ToastComponent):
    """Radix toast title."""

    tag = "Title"
    alias = "ToastTitle"

    as_child: Var[bool]


class ToastDescription(ToastComponent):
    """Radix toast description."""

    tag = "Description"
    alias = "ToastDescription"

    as_child: Var[bool]


class ToastClose(ToastComponent):
    """Radix toast close."""

    tag = "Close"
    alias = "ToastClose"

    as_child: Var[bool]


class ToastAction(ToastComponent):
    """Radix toast action."""

    tag = "Action"
    alias = "ToastAction"

    as_child: Var[bool]
    alt_text: Var[str]
