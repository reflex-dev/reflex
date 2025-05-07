"""Interactive components provided by @radix-ui/themes."""

from __future__ import annotations

from typing import Literal

from reflex.components.component import Component
from reflex.components.core.breakpoints import Responsive
from reflex.components.core.match import Match
from reflex.components.el import elements
from reflex.components.lucide import Icon
from reflex.style import Style
from reflex.vars.base import Var

from ..base import (
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

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Button size "1" - "4"
    size: Var[Responsive[LiteralButtonSize]]

    # Variant of button: "classic" | "solid" | "soft" | "surface" | "outline" | "ghost"
    variant: Var[LiteralVariant]

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the button with higher contrast color against background
    high_contrast: Var[bool]

    # Override theme radius for button: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a IconButton component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Raises:
            ValueError: If no children are passed.

        Returns:
            The IconButton component.
        """
        if children:
            if isinstance(children[0], str):
                children = [
                    Icon.create(
                        children[0],
                    )
                ]
        else:
            raise ValueError(
                "IconButton requires a child icon. Pass a string as the first child or a rx.icon."
            )
        if "size" in props:
            if isinstance(props["size"], str):
                children[0].size = RADIX_TO_LUCIDE_SIZE[props["size"]]
            else:
                size_map_var = Match.create(
                    props["size"],
                    *list(RADIX_TO_LUCIDE_SIZE.items()),
                    12,
                )
                if not isinstance(size_map_var, Var):
                    raise ValueError(f"Match did not return a Var: {size_map_var}")
                children[0].size = size_map_var
        return super().create(*children, **props)

    def add_style(self):
        """Add style to the component.

        Returns:
            The style of the component.
        """
        return Style({"padding": "6px"})


icon_button = IconButton.create
