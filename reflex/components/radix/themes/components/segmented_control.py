"""SegmentedControl from Radix Themes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import List, Literal, Union

from reflex.components.core.breakpoints import Responsive
from reflex.event import EventHandler
from reflex.vars import Var

from ..base import LiteralAccentColor, RadixThemesComponent


class SegmentedControlRoot(RadixThemesComponent):
    """Root element for a SegmentedControl component."""

    tag = "SegmentedControl.Root"

    # The size of the segmented control: "1" | "2" | "3"
    size: Var[Responsive[Literal["1", "2", "3"]]]

    # Variant of button: "classic" | "surface"
    variant: Var[Literal["classic", "surface"]]

    type: Var[Literal["single", "multiple"]]

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # The radius of the segmented control: "none" | "small" | "medium" | "large" | "full"
    radius: Var[Literal["none", "small", "medium", "large", "full"]]

    # The default value of the segmented control.
    default_value: Var[Union[str, List[str]]]

    value: Var[Union[str, List[str]]]

    on_change: EventHandler[lambda e0: [e0]]

    _rename_props = {"onChange": "onValueChange"}


class SegmentedControlItem(RadixThemesComponent):
    """An item in the SegmentedControl component."""

    tag = "SegmentedControl.Item"

    # The value of the item.
    value: Var[str]

    _valid_parents: List[str] = ["SegmentedControlRoot"]


class SegmentedControl(SimpleNamespace):
    """SegmentedControl components namespace."""

    root = staticmethod(SegmentedControlRoot.create)
    item = staticmethod(SegmentedControlItem.create)


segmented_control = SegmentedControl()
