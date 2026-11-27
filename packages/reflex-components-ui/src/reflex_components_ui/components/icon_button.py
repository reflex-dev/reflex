"""An icon button: a button that holds a single icon."""

from __future__ import annotations

from typing import ClassVar

from reflex_base.components.component import Component, field
from reflex_base.style import Style
from reflex_base.vars.base import Var
from reflex_components_core.core.match import Match
from reflex_components_lucide import Icon

from reflex_components_ui.components.button import BaseButton
from reflex_components_ui.props import LiteralVariant
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.button import ICON_BUTTON

RADIX_TO_LUCIDE_SIZE = {"1": 12, "2": 24, "3": 36, "4": 48}


class IconButton(BaseButton):
    """A button designed specifically for usage with a single icon."""

    styles: ClassVar[ComponentStyles] = ICON_BUTTON

    variant: Var[LiteralVariant] = field(
        doc='Variant of button: "classic" | "solid" | "soft" | "surface" | "outline" | "ghost"'
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
