"""Components for the CheckboxGroup component of Radix Themes."""

from collections.abc import Sequence
from types import SimpleNamespace
from typing import Literal

from reflex_base.components.component import field
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent


class CheckboxGroupRoot(RadixThemesComponent):
    """Root element for a CheckboxGroup component."""

    tag = "CheckboxGroup.Root"
    _is_form_control = True

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

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

    value: Var[Sequence[str]] = field(
        doc="The controlled value of the checked checkboxes. Should be used in conjunction with on_value_change."
    )

    name: Var[str] = field(
        doc="used to assign a name to the entire group of checkboxes"
    )

    disabled: Var[bool] = field(doc="Whether the checkbox group is disabled")

    required: Var[bool] = field(doc="Whether the checkbox group is required")

    orientation: Var[Literal["horizontal", "vertical"]] = field(
        doc="The orientation of the component."
    )

    dir: Var[Literal["ltr", "rtl"]] = field(
        doc="The reading direction of the checkbox group. If omitted, inherits globally from DirectionProvider or assumes LTR (left-to-right) reading mode."
    )

    loop: Var[bool] = field(
        doc="When true, keyboard navigation will loop from last item to first, and vice versa."
    )

    on_value_change: EventHandler[passthrough_event_spec(list[str])] = field(
        doc="Fired when the set of checked checkboxes changes."
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

    required: Var[bool] = field(
        doc="When true, indicates that the user must check the checkbox item before the owning form can be submitted."
    )


class CheckboxGroup(SimpleNamespace):
    """CheckboxGroup components namespace."""

    root = staticmethod(CheckboxGroupRoot.create)
    item = staticmethod(CheckboxGroupItem.create)


checkbox_group = CheckboxGroup()
