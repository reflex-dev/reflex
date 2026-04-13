"""SegmentedControl from Radix Themes."""

from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace
from typing import ClassVar, Literal

from reflex_base.components.component import field
from reflex_base.event import EventHandler
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent


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

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        doc='The size of the segmented control: "1" | "2" | "3"'
    )

    variant: Var[Literal["classic", "surface"]] = field(
        doc='Variant of button: "classic" | "surface"'
    )

    type: Var[Literal["single", "multiple"]] = field(
        doc='The type of the segmented control, either "single" for selecting one option or "multiple" for selecting multiple options.'
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="Override theme color for button")

    radius: Var[Literal["none", "small", "medium", "large", "full"]] = field(
        doc='The radius of the segmented control: "none" | "small" | "medium" | "large" | "full"'
    )

    default_value: Var[str | Sequence[str]] = field(
        doc="The default value of the segmented control."
    )

    value: Var[str | Sequence[str]] = field(
        doc="The current value of the segmented control."
    )

    on_change: EventHandler[on_value_change] = field(
        doc="Handles the `onChange` event for the SegmentedControl component."
    )

    _rename_props = {"onChange": "onValueChange"}


class SegmentedControlItem(RadixThemesComponent):
    """An item in the SegmentedControl component."""

    tag = "SegmentedControl.Item"

    value: Var[str] = field(doc="The value of the item.")

    _valid_parents: ClassVar[list[str]] = ["SegmentedControlRoot"]


class SegmentedControl(SimpleNamespace):
    """SegmentedControl components namespace."""

    root = staticmethod(SegmentedControlRoot.create)
    item = staticmethod(SegmentedControlItem.create)


segmented_control = SegmentedControl()
