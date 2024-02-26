"""Declarative layout and common spacing props."""
from __future__ import annotations

from typing import Literal

from reflex import el
from reflex.vars import Var

from ..base import RadixThemesComponent

LiteralSectionSize = Literal["1", "2", "3"]


class Section(el.Section, RadixThemesComponent):
    """Denotes a section of page content."""

    tag = "Section"

    # The size of the section: "1" - "3" (default "3")
    size: Var[LiteralSectionSize]
