"""A separator: a line between two things."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from reflex_base.components.component import field
from reflex_base.components.tags import CommonTag
from reflex_base.vars.base import LiteralVar, Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_ui.base import UIComponent
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.separator import SEPARATOR
from reflex_components_ui.themes import LiteralAccentColor

LiteralSeparatorSize = Literal["1", "2", "3", "4"]


class Separator(UIComponent):
    """Visually or semantically separates content."""

    tag = "span"

    styles: ClassVar[ComponentStyles] = SEPARATOR

    size: Var[Responsive[LiteralSeparatorSize]] = field(
        default=LiteralVar.create("4"),
        doc='The size of the separator: "1" | "2" | "3" | "4"',
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="The color of the separator")

    orientation: Var[Responsive[Literal["horizontal", "vertical"]]] = field(
        doc="The orientation of the separator."
    )

    decorative: Var[bool] = field(
        doc="When true, signifies that it is purely visual, carries no semantic meaning, and ensures it is not present in the accessibility tree."
    )

    def _exclude_props(self) -> list[str]:
        """Keep the props that are not attributes off the element.

        Returns:
            The props read as styles, and the one read as the role.
        """
        return [*super()._exclude_props(), "decorative"]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the line, with the role of a separator unless it is decorative.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag.
        """
        tag = super()._render(props)
        decorative = self.decorative
        if decorative is None:
            return tag
        if isinstance(decorative, LiteralVar):
            return tag if decorative._var_value else tag.add_props(role="separator")
        role = Var(f'({decorative!s} ? undefined : "separator")')
        return tag.add_props(role=role._replace(merge_var_data=decorative._get_all_var_data()))


# Alias to divider.
divider = separator = Separator.create
