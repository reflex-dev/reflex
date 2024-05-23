"""Base components."""
import sys

import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={"app_wrap", "bare"},
    submod_attrs={
        "body": ["Body"],
        "document": ["DocumentHead", "Html", "Main", "NextScript"],
        "fragment": [
            "Fragment",
            "fragment",
        ],
        "head": [
            "head",
            "Head",
        ],
        "link": ["RawLink", "ScriptTag"],
        "meta": ["Description", "Image", "Meta", "Title"],
        "script": ["Script", "script"],
    },
)
