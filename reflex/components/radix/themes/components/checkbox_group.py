"""Components for the CheckboxGroup component of Radix Themes."""

from types import SimpleNamespace
from typing import Literal

from reflex.vars import Var

from ..base import LiteralAccentColor, RadixThemesComponent


class CheckboxGroupRoot(RadixThemesComponent):
    """Root element for a CheckboxGroup component."""

    tag = "CheckboxGroup"

    #
    size: Var[Literal["1", "2", "3"]]

    # Variant of button: "classic" | "surface" | "soft"
    variant: Var[Literal["classic", "surface", "soft"]]

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # Uses a higher contrast color for the component.
    high_contrast: Var[bool]


class CheckboxGroupItem(RadixThemesComponent):
    """An item in the CheckboxGroup component."""

    tag = "CheckboxGroup.Item"


class CheckboxGroup(SimpleNamespace):
    """CheckboxGroup components namespace."""

    root = staticmethod(CheckboxGroupRoot.create)
    item = staticmethod(CheckboxGroupItem.create)


checkbox_group = CheckboxGroup()
