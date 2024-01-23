"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""
from __future__ import annotations

from reflex import el

from ..base import (
    RadixThemesComponent,
)


class Quote(el.Q, RadixThemesComponent):
    """A short inline quotation."""

    tag = "Quote"
