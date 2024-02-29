"""Tooltip components."""
from __future__ import annotations

from typing import Any, Optional, Union

from reflex.components.chakra import ChakraComponent, LiteralChakraDirection
from reflex.vars import Var


class Tooltip(ChakraComponent):
    """A tooltip message to appear."""

    tag = "Tooltip"

    # The padding required to prevent the arrow from reaching the very edge of the popper.
    arrow_padding: Optional[Var[int]] = None

    # The color of the arrow shadow.
    arrow_shadow_color: Optional[Var[str]] = None

    # Size of the arrow.
    arrow_size: Optional[Var[int]] = None

    # Delay (in ms) before hiding the tooltip
    delay: Optional[Var[int]] = None

    # If true, the tooltip will hide on click
    close_on_click: Optional[Var[bool]] = None

    # If true, the tooltip will hide on pressing Esc key
    close_on_esc: Optional[Var[bool]] = None

    # If true, the tooltip will hide while the mouse is down
    close_on_mouse_down: Optional[Var[bool]] = None

    # If true, the tooltip will be initially shown
    default_is_open: Optional[Var[bool]] = None

    # Theme direction ltr or rtl. Popper's placement will be set accordingly
    direction: Optional[Var[LiteralChakraDirection]] = None

    # The distance or margin between the reference and popper. It is used internally to create an offset modifier. NB: If you define offset prop, it'll override the gutter.
    gutter: Optional[Var[int]] = None

    # If true, the tooltip will show an arrow tip
    has_arrow: Optional[Var[bool]] = None

    # If true, the tooltip with be disabled.
    is_disabled: Optional[Var[bool]] = None

    # If true, the tooltip will be open.
    is_open: Optional[Var[bool]] = None

    # The label of the tooltip
    label: Optional[Var[str]] = None

    # Delay (in ms) before showing the tooltip
    open_delay: Optional[Var[int]] = None

    # The placement of the popper relative to its reference.
    placement: Optional[Var[str]] = None

    # If true, the tooltip will wrap its children in a `<span/>` with `tabIndex=0`
    should_wrap_children: Optional[Var[bool]] = None

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_close": lambda: [],
            "on_open": lambda: [],
        }
