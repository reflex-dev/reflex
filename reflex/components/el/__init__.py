"""The el package exports raw HTML elements."""
from . import elements

import lazy_loader as lazy

m={f"elements.{k}":v for k,v in elements.MAP.items()}
__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={"elements"},
    submod_attrs=m
    # submod_attrs={
    #     # "base": [
    #     #     "Fragment",
    #     #     "fragment",
    #     #     "Script",
    #     #     "fragment",
    #     #     "script",
    #     # ],
    #     "component": [
    #         "Component",
    #         "NoSSRComponent",
    #     ],
    #     "next": [
    #         "NextLink",
    #         "next_link"
    #     ],
    #     # "el.elements": [
    #     #     "img as image",
    #     # ],
    # },
)