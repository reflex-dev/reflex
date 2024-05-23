"""Typographic components."""

from .blockquote import Blockquote
from .code import Code
from .heading import Heading
from .link import Link
from .text import text

blockquote = Blockquote.create
code = Code.create
heading = Heading.create
link = Link.create

__all__ = [
    "blockquote",
    "code",
    "heading",
    "link",
    "text",
]
