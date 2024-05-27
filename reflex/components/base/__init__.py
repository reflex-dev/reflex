"""Base components."""
from __future__ import annotations

from reflex.utils import lazy_loader

_SUBMODULES: set[str] = {"app_wrap", "bare"}

_SUBMOD_ATTRS: dict[str, list[str]] = {
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
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
