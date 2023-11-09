"""Declarative layout and common spacing props."""
from __future__ import annotations

from typing import Literal

from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAlign,
    LiteralJustify,
    LiteralSize,
    RadixThemesComponent,
)

from .base import (
    LayoutComponent
)

LiteralContainerSize = Literal["1", "2", "3", "4"]


class Container(LayoutComponent):
    """Constrains the maximum width of page content.

    See https://www.radix-ui.com/themes/docs/components/container
    """

    tag = "Container"

    # The size of the container: "1" - "4" (default "4")
    size: Var[LiteralContainerSize]
