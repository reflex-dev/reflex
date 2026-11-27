"""A box: the plain element other layouts are built from."""

from __future__ import annotations

from typing import ClassVar

from reflex_components_core.el import elements

from reflex_components_ui.base import UIComponent
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.box import BOX


class Box(UIComponent, elements.Div):
    """A fundamental layout building block, based on `div` element."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = BOX


box = Box.create
