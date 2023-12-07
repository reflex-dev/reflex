"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""
from __future__ import annotations

from reflex import el

from ..base import (
    CommonMarginProps,
    RadixThemesComponent,
)


class Em(el.Em, CommonMarginProps, RadixThemesComponent):
    """Marks text to stress emphasis."""

    tag = "Em"
