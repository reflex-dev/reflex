"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex import el
from reflex.components.component import Component
from reflex.components.forms.debounce import DebounceInput
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAccentColor,
    LiteralRadius,
    LiteralSize,
    LiteralVariant,
    RadixThemesComponent,
)


class ContextMenuRoot(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Root"

class ContextMenuTrigger(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Trigger"

class ContextMenuContent(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Content"

    # Button size "1" - "4"
    size: Var[Literal["1", "2"]]

    # Variant of button: "solid" | "soft" | "outline" | "ghost"
    variant: Var[Literal["solid", "soft"]]

    # Override theme color for button
    color: Var[LiteralAccentColor]

    # Whether to render the button with higher contrast color against background
    high_contrast: Var[bool]

class ContextMenuSubTrigger(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.SubTrigger"

class ContextMenuSubContent(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.SubContent"


class ContextMenuItem(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Item"

    # Override theme color for button
    color: Var[LiteralAccentColor]


    # Shortcut to render a menu item as a link
    shortcut: Var[str]


class ContextMenuSeparator(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ContextMenu.Separator"
