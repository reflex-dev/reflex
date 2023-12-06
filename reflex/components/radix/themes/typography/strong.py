"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""
from __future__ import annotations

from reflex import el

from ..base import (
    CommonMarginProps,
    RadixThemesComponent,
)


class Strong(el.Strong, CommonMarginProps, RadixThemesComponent):
    """Marks text to signify strong importance."""

    tag = "Strong"
