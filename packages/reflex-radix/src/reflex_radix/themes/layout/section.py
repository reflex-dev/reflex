"""Declarative layout and common spacing props."""

from __future__ import annotations

from typing import Literal

from reflex_components.core.breakpoints import Responsive
from reflex_components.el import elements

from reflex.components.component import field
from reflex.vars.base import LiteralVar, Var
from reflex_radix.themes.base import RadixThemesComponent

LiteralSectionSize = Literal["1", "2", "3"]


class Section(elements.Section, RadixThemesComponent):
    """Denotes a section of page content."""

    tag = "Section"

    size: Var[Responsive[LiteralSectionSize]] = field(
        default=LiteralVar.create("2"),
        doc='The size of the section: "1" - "3" (default "2")',
    )


section = Section.create
