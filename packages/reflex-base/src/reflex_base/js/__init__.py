"""Run JavaScript in the browser through a defined API."""

from typing import TYPE_CHECKING

from reflex_base.utils import lazy_loader

if TYPE_CHECKING:
    from .environment import ScriptEnvVar, env
    from .modules import JsFunction

    __all__ = ["JsFunction", "ScriptEnvVar", "env"]

# Lazy, so `import reflex`, which installs the module finder, does not load the
# event and var systems.
_SUBMODULES: set[str] = {"environment", "finder", "modules"}
_SUBMOD_ATTRS: lazy_loader.SubmodAttrsType = {
    "environment": ["ScriptEnvVar", "env"],
    "modules": ["JsFunction"],
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
