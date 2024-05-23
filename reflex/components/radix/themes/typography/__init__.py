"""Typographic components."""

# from .blockquote import Blockquote
# from .code import Code
# from .heading import Heading
# from .link import Link
# from .text import text
#
# blockquote = Blockquote.create
# code = Code.create
# heading = Heading.create
# link = Link.create
#
# __all__ = [
#     "blockquote",
#     "code",
#     "heading",
#     "link",
#     "text",
# ]

import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submod_attrs={
        "blockquote": [
            "blockquote",
            "Blockquote",
        ],
        "code": [
            "code",
            "Code",
        ],
        "heading": [
            "heading",
            "Heading"
        ],
        "link": [
            "link",
            "Link"
        ],
        "text": ["text"]
    },
)
