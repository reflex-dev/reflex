"""Built-in compiler plugins for single-pass page compilation."""

from reflex_base.plugins import (
    BaseContext,
    CompileContext,
    CompilerHooks,
    ComponentAndChildren,
    PageContext,
)

from .builtin import (
    ApplyStylePlugin,
    ClientStateScopePlugin,
    DefaultCollectorPlugin,
    DefaultPagePlugin,
    InlineLifecyclePlugin,
    default_page_plugins,
)
from .memoize import MemoizeStatefulPlugin

__all__ = [
    "ApplyStylePlugin",
    "BaseContext",
    "ClientStateScopePlugin",
    "CompileContext",
    "CompilerHooks",
    "ComponentAndChildren",
    "DefaultCollectorPlugin",
    "DefaultPagePlugin",
    "InlineLifecyclePlugin",
    "MemoizeStatefulPlugin",
    "PageContext",
    "default_page_plugins",
]
