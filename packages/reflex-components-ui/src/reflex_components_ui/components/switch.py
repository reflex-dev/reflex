"""A switch: a native checkbox with the role of a switch."""

from __future__ import annotations

import functools
from typing import Any, ClassVar, Literal

from reflex_base.components.component import field
from reflex_base.components.tags import CommonTag
from reflex_base.event import EventHandler, checked_input_event
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_ui.components.checkbox import CheckedInput
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.switch import SWITCH
from reflex_components_ui.themes import LiteralAccentColor

LiteralSwitchSize = Literal["1", "2", "3"]


class Switch(CheckedInput):
    """A toggle switch alternative to the checkbox."""

    styles: ClassVar[ComponentStyles] = SWITCH

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

    on_change: EventHandler[checked_input_event] = field(
        doc="Fired when the value of the switch changes"
    )

    @classmethod
    @functools.cache
    def _literal_props(cls) -> dict[str, tuple[str, ...]]:
        """Get the props that take listed values.

        Returns:
            The values of each such prop, the radius among them: a switch has
            fewer than a theme.
        """
        return {
            **super()._literal_props(),  # pyright: ignore[reportAttributeAccessIssue]
            "radius": ("none", "small", "full"),
        }

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the input as a switch.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the role that says on and off rather than checked.
        """
        return super()._render(props).add_props(role="switch")


switch = Switch.create
