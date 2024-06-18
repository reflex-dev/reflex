"""SegmentedControl from Radix Themes."""

from types import SimpleNamespace
from typing import Literal

from reflex.vars import Var

from ..base import LiteralAccentColor, RadixThemesComponent


class SegmentedControlRoot(RadixThemesComponent):
    """Root element for a SegmentedControl component."""

    tag = "SegmentedControl"

    # The size of the segmented control: "1" | "2" | "3"
    size: Var[Literal["1", "2", "3"]]

    # Variant of button: "classic" | "surface" | "soft"
    variant: Var[Literal["classic", "surface", "soft"]]

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # The radius of the segmented control: "none" | "small" | "medium" | "large" | "full"
    radius: Var[Literal["none", "small", "medium", "large", "full"]]

    # The default value of the segmented control.
    default_value: Var[str]


class SegmentedControlItem(RadixThemesComponent):
    """An item in the SegmentedControl component."""

    tag = "SegmentedControl.Item"

    # The value of the item.
    value: Var[str]


class SegmentedControl(SimpleNamespace):
    """SegmentedControl components namespace."""

    root = staticmethod(SegmentedControlRoot.create)
    item = staticmethod(SegmentedControlItem.create)


segmented_control = SegmentedControl()
