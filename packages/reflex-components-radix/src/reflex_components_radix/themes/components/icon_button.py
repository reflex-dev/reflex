"""Interactive components provided by @radix-ui/themes."""

from __future__ import annotations

from typing import Literal

from reflex_base.components.component import Component, field
from reflex_base.style import Style
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.match import Match
from reflex_components_core.el import elements
from reflex_components_lucide import Icon

from reflex_components_radix.themes.base import (
    LiteralAccentColor,
    LiteralRadius,
    LiteralVariant,
    RadixLoadingProp,
    RadixThemesComponent,
)

LiteralButtonSize = Literal["1", "2", "3", "4"]

RADIX_TO_LUCIDE_SIZE = {"1": 12, "2": 24, "3": 36, "4": 48}


class IconButton(elements.Button, RadixLoadingProp, RadixThemesComponent):
    """A button designed specifically for usage with a single icon."""

    tag = "IconButton"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    size: Var[Responsive[LiteralButtonSize]] = field(doc='Button size "1" - "4"')

    variant: Var[LiteralVariant] = field(
        doc='Variant of button: "classic" | "solid" | "soft" | "surface" | "outline" | "ghost"'
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="Override theme color for button")

    high_contrast: Var[bool] = field(
        doc="Whether to render the button with higher contrast color against background"
    )

    radius: Var[LiteralRadius] = field(
        doc='Override theme radius for button: "none" | "small" | "medium" | "large" | "full"'
    )

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a IconButton component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The IconButton component.

        Raises:
            ValueError: If no children are passed.
        """
        if children:
            if isinstance(children[0], str):
                children = [
                    Icon.create(
                        children[0],
                    )
                ]
        else:
            msg = "IconButton requires a child icon. Pass a string as the first child or a rx.icon."
            raise ValueError(msg)
        if "size" in props:
            if isinstance(props["size"], str):
                children[0].size = RADIX_TO_LUCIDE_SIZE[props["size"]]  # pyright: ignore[reportAttributeAccessIssue]
            else:
                size_map_var = Match.create(
                    props["size"],
                    *list(RADIX_TO_LUCIDE_SIZE.items()),
                    12,
                )
                if not isinstance(size_map_var, Var):
                    msg = f"Match did not return a Var: {size_map_var}"
                    raise ValueError(msg)
                children[0].size = size_map_var  # pyright: ignore[reportAttributeAccessIssue]
        return super().create(*children, **props)

    def add_style(self):
        """Add style to the component.

        Returns:
            The style of the component.
        """
        return Style({"padding": "6px"})


icon_button = IconButton.create
