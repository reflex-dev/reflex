"""Compiler plugin foundations for single-pass page compilation."""

from reflex.compiler.plugins.base import (
    BaseContext,
    CompileComponentYield,
    CompileContext,
    CompilerHooks,
    CompilerPlugin,
    ComponentAndChildren,
    PageContext,
    PageDefinition,
)
from reflex.compiler.plugins.builtin import (
    ApplyStylePlugin,
    ConsolidateAppWrapPlugin,
    ConsolidateCustomCodePlugin,
    ConsolidateDynamicImportsPlugin,
    ConsolidateHooksPlugin,
    ConsolidateImportsPlugin,
    ConsolidateRefsPlugin,
    DefaultPagePlugin,
    default_page_plugins,
)

__all__ = [
    "ApplyStylePlugin",
    "BaseContext",
    "CompileComponentYield",
    "CompileContext",
    "CompilerHooks",
    "CompilerPlugin",
    "ComponentAndChildren",
    "ConsolidateAppWrapPlugin",
    "ConsolidateCustomCodePlugin",
    "ConsolidateDynamicImportsPlugin",
    "ConsolidateHooksPlugin",
    "ConsolidateImportsPlugin",
    "ConsolidateRefsPlugin",
    "DefaultPagePlugin",
    "PageContext",
    "PageDefinition",
    "default_page_plugins",
]
