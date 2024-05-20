"""Namespace for components provided by @radix-ui packages."""
import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={"themes", "primitives"},
)