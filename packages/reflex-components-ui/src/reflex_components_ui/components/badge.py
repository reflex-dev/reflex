"""A badge: a short label that stands out."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_ui.base import UIComponent
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.badge import BADGE
from reflex_components_ui.themes import LiteralAccentColor, LiteralRadius


class Badge(UIComponent, elements.Span):
    """A stylized badge element."""

    tag = "span"

    styles: ClassVar[ComponentStyles] = BADGE

    variant: Var[Literal["solid", "soft", "surface", "outline"]] = field(
        doc="The variant of the badge"
    )

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(doc="The size of the badge")

    color_scheme: Var[LiteralAccentColor] = field(doc="Color theme of the badge")

    high_contrast: Var[bool] = field(
        doc="Whether to render the badge with higher contrast color against background"
    )

    radius: Var[LiteralRadius] = field(
        doc='Override theme radius for badge: "none" | "small" | "medium" | "large" | "full"'
    )


badge = Badge.create
