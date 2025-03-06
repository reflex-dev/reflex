"""SegmentedControl from Radix Themes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar, Literal, Sequence

from reflex.components.core.breakpoints import Responsive
from reflex.event import EventHandler
from reflex.vars.base import Var

from ..base import LiteralAccentColor, RadixThemesComponent


def on_value_change(
    value: Var[str | list[str]],
) -> tuple[Var[str | list[str]]]:
    """Handle the on_value_change event.

    Args:
        value: The value of the event.

    Returns:
        The value of the event.
    """
    return (value,)


class SegmentedControlRoot(RadixThemesComponent):
    """Root element for a SegmentedControl component."""

    tag = "SegmentedControl.Root"

    # The size of the segmented control: "1" | "2" | "3"
    size: Var[Responsive[Literal["1", "2", "3"]]]

    # Variant of button: "classic" | "surface"
    variant: Var[Literal["classic", "surface"]]

    # The type of the segmented control, either "single" for selecting one option or "multiple" for selecting multiple options.
    type: Var[Literal["single", "multiple"]]

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # The radius of the segmented control: "none" | "small" | "medium" | "large" | "full"
    radius: Var[Literal["none", "small", "medium", "large", "full"]]

    # The default value of the segmented control.
    default_value: Var[str | Sequence[str]]

    # The current value of the segmented control.
    value: Var[str | Sequence[str]]

    # Handles the `onChange` event for the SegmentedControl component.
    on_change: EventHandler[on_value_change]

    _rename_props = {"onChange": "onValueChange"}


class SegmentedControlItem(RadixThemesComponent):
    """An item in the SegmentedControl component."""

    tag = "SegmentedControl.Item"

    # The value of the item.
    value: Var[str]

    _valid_parents: ClassVar[list[str]] = ["SegmentedControlRoot"]


class SegmentedControl(SimpleNamespace):
    """SegmentedControl components namespace."""

    root = staticmethod(SegmentedControlRoot.create)
    item = staticmethod(SegmentedControlItem.create)


segmented_control = SegmentedControl()
