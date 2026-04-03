"""Built-in compiler plugins for single-pass page compilation."""

from reflex_core.plugins import (
    BaseContext,
    CompileContext,
    CompilerHooks,
    CompilerPlugin,
    ComponentAndChildren,
    PageContext,
    PageDefinition,
)

from .builtin import (
    ApplyStylePlugin,
    DefaultCollectorPlugin,
    DefaultPagePlugin,
    default_page_plugins,
)

__all__ = [
    "ApplyStylePlugin",
    "BaseContext",
    "CompileContext",
    "CompilerHooks",
    "CompilerPlugin",
    "ComponentAndChildren",
    "DefaultCollectorPlugin",
    "DefaultPagePlugin",
    "PageContext",
    "PageDefinition",
    "default_page_plugins",
]
