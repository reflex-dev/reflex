"""A box: the plain element other layouts are built from."""

from __future__ import annotations

from typing import ClassVar

from reflex_components_ui.base import ComponentStyles, UIComponent
from reflex_components_ui.styles.box import BOX


class Box(UIComponent):
    """A block element with no look of its own."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = BOX


box = Box.create
