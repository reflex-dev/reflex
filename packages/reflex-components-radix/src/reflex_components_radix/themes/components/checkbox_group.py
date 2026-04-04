"""Components for the CheckboxGroup component of Radix Themes."""

from collections.abc import Sequence
from types import SimpleNamespace
from typing import Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent


class CheckboxGroupRoot(RadixThemesComponent):
    """Root element for a CheckboxGroup component."""

    tag = "CheckboxGroup.Root"

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        doc="Use the size prop to control the checkbox size."
    )

    variant: Var[Literal["classic", "surface", "soft"]] = field(
        doc='Variant of button: "classic" | "surface" | "soft"'
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="Override theme color for button")

    high_contrast: Var[bool] = field(
        doc="Uses a higher contrast color for the component."
    )

    default_value: Var[Sequence[str]] = field(
        doc="determines which checkboxes, if any, are checked by default."
    )

    name: Var[str] = field(
        doc="used to assign a name to the entire group of checkboxes"
    )


class CheckboxGroupItem(RadixThemesComponent):
    """An item in the CheckboxGroup component."""

    tag = "CheckboxGroup.Item"

    value: Var[str] = field(
        doc="specifies the value associated with a particular checkbox option."
    )

    disabled: Var[bool] = field(
        doc="Use the native disabled attribute to create a disabled checkbox."
    )


class CheckboxGroup(SimpleNamespace):
    """CheckboxGroup components namespace."""

    root = staticmethod(CheckboxGroupRoot.create)
    item = staticmethod(CheckboxGroupItem.create)


checkbox_group = CheckboxGroup()
