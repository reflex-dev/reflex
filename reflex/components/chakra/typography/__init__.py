"""Typography components."""

from reflex.components.component import Component

from .heading import Heading
from .highlight import Highlight
from .span import Span
from .text import Text

__all__ = [f for f in dir() if f[0].isupper() or f in ("span",)]  # type: ignore
