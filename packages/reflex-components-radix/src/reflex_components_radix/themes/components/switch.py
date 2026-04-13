"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex_base.components.component import field
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent

LiteralSwitchSize = Literal["1", "2", "3"]


class Switch(RadixThemesComponent):
    """A toggle switch alternative to the checkbox."""

    tag = "Switch"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    default_checked: Var[bool] = field(doc="Whether the switch is checked by default")

    checked: Var[bool] = field(doc="Whether the switch is checked")

    disabled: Var[bool] = field(
        doc="If true, prevent the user from interacting with the switch"
    )

    required: Var[bool] = field(
        doc="If true, the user must interact with the switch to submit the form"
    )

    name: Var[str] = field(doc="The name of the switch (when submitting a form)")

    value: Var[str] = field(doc='The value associated with the "on" position')

    size: Var[Responsive[LiteralSwitchSize]] = field(doc='Switch size "1" - "4"')

    variant: Var[Literal["classic", "surface", "soft"]] = field(
        doc='Variant of switch: "classic" | "surface" | "soft"'
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="Override theme color for switch")

    high_contrast: Var[bool] = field(
        doc="Whether to render the switch with higher contrast color against background"
    )

    radius: Var[Literal["none", "small", "full"]] = field(
        doc='Override theme radius for switch: "none" | "small" | "full"'
    )

    # Props to rename
    _rename_props = {"onChange": "onCheckedChange"}

    on_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the value of the switch changes"
    )


switch = Switch.create
