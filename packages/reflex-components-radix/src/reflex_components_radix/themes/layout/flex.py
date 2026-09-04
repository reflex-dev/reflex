"""Declarative layout and common spacing props."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_radix.themes.base import (
    LiteralAlign,
    LiteralJustify,
    LiteralSpacing,
    RadixThemesComponent,
)

LiteralFlexDirection = Literal["row", "column", "row-reverse", "column-reverse"]
LiteralFlexWrap = Literal["nowrap", "wrap", "wrap-reverse"]


class Flex(elements.Div, RadixThemesComponent):
    """Component for creating flex layouts."""

    tag = "Flex"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    direction: Var[Responsive[LiteralFlexDirection]] = field(
        doc='How child items are laid out: "row" | "column" | "row-reverse" | "column-reverse"'
    )

    align: Var[Responsive[LiteralAlign]] = field(
        doc='Alignment of children along the main axis: "start" | "center" | "end" | "baseline" | "stretch"'
    )

    justify: Var[Responsive[LiteralJustify]] = field(
        doc='Alignment of children along the cross axis: "start" | "center" | "end" | "between"'
    )

    wrap: Var[Responsive[LiteralFlexWrap]] = field(
        doc='Whether children should wrap when they reach the end of their container: "nowrap" | "wrap" | "wrap-reverse"'
    )

    spacing: Var[Responsive[LiteralSpacing]] = field(
        doc='Gap between children: "0" - "9"'
    )

    # Reflex maps the "spacing" prop to "gap" prop.
    _rename_props: ClassVar[dict[str, str]] = {"spacing": "gap"}


flex = Flex.create
