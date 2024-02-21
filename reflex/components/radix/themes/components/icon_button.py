"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex import el
from reflex.components.component import Component
from reflex.components.core.match import Match
from reflex.components.lucide import Icon
from reflex.style import Style
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    LiteralRadius,
    LiteralVariant,
    RadixThemesComponent,
)

LiteralButtonSize = Literal["1", "2", "3", "4"]


class IconButton(el.Button, RadixThemesComponent):
    """A button designed specifically for usage with a single icon."""

    tag = "IconButton"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Button size "1" - "4"
    size: Var[LiteralButtonSize]

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
            if type(children[0]) == str:
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
            if type(props["size"]) == str:
                RADIX_TO_LUCIDE_SIZE = {
                    "1": "12px",
                    "2": "24px",
                    "3": "36px",
                    "4": "48px",
                }
                children[0].size = RADIX_TO_LUCIDE_SIZE[props["size"]]
            else:
                children[0].size = Match.create(
                    props["size"],
                    ("1", "12px"),
                    ("2", "24px"),
                    ("3", "36px"),
                    ("4", "48px"),
                    "12px",
                )
        return super().create(*children, **props)

    def _apply_theme(self, theme: Component):
        self.style = Style({"padding": "6px", **self.style})


icon_button = IconButton.create
