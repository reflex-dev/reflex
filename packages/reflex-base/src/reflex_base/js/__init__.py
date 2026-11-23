"""Build calls on ``reflex``, the API browser code reaches Reflex through."""

from reflex_base.utils import lazy_loader

# Not imported from typing, which `import reflex` does not load otherwise.
TYPE_CHECKING = False
if TYPE_CHECKING:
    from .api import library, ref

    __all__ = ["library", "ref"]

# Lazy: the module finder `import reflex` registers lives in this package, and
# loading it must not load the event and var systems.
__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__, submod_attrs={"api": ["library", "ref"]}
)
