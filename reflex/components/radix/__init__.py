"""Namespace for components provided by @radix-ui packages."""

# from .primitives import *
# from .themes import *
# from . import primitives
# from . import themes

import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={"themes", "primitives"},
    # submod_attrs={
    #     "base": [
    #         "Fragment",
    #         "fragment",
    #         "Script",
    #         "fragment",
    #         "script",
    #     ],
    #     "component": [
    #         "Component",
    #         "NoSSRComponent",
    #     ],
    #     "next": [
    #         "NextLink",
    #         "next_link"
    #     ],
    #     "el": [
    #         "img",
    #     ],
    # },
)