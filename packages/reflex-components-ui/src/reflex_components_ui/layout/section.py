"""A section of a page."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import field
from reflex_base.vars.base import LiteralVar, Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_ui.base import UIComponent
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.section import SECTION

LiteralSectionSize = Literal["1", "2", "3"]


class Section(UIComponent, elements.Section):
    """Denotes a section of page content."""

    tag = "section"

    styles: ClassVar[ComponentStyles] = SECTION

    size: Var[Responsive[LiteralSectionSize]] = field(
        default=LiteralVar.create("2"),
        doc='The size of the section: "1" - "3" (default "2")',
    )


section = Section.create
