"""Components for the CheckboxGroup component of Radix Themes."""

from types import SimpleNamespace
from typing import Literal, Sequence

from reflex.components.core.breakpoints import Responsive
from reflex.vars.base import Var

from ..base import LiteralAccentColor, RadixThemesComponent


class CheckboxGroupRoot(RadixThemesComponent):
    """Root element for a CheckboxGroup component."""

    tag = "CheckboxGroup.Root"

    # Use the size prop to control the checkbox size.
    size: Var[Responsive[Literal["1", "2", "3"]]]

    # Variant of button: "classic" | "surface" | "soft"
    variant: Var[Literal["classic", "surface", "soft"]]

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # Uses a higher contrast color for the component.
    high_contrast: Var[bool]

    # determines which checkboxes, if any, are checked by default.
    default_value: Var[Sequence[str]]

    # used to assign a name to the entire group of checkboxes
    name: Var[str]


class CheckboxGroupItem(RadixThemesComponent):
    """An item in the CheckboxGroup component."""

    tag = "CheckboxGroup.Item"

    # specifies the value associated with a particular checkbox option.
    value: Var[str]

    # Use the native disabled attribute to create a disabled checkbox.
    disabled: Var[bool]


class CheckboxGroup(SimpleNamespace):
    """CheckboxGroup components namespace."""

    root = staticmethod(CheckboxGroupRoot.create)
    item = staticmethod(CheckboxGroupItem.create)


checkbox_group = CheckboxGroup()
