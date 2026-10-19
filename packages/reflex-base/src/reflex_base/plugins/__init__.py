"""Reflex Plugin System."""

from typing import TYPE_CHECKING

from reflex_base.utils import lazy_loader

if TYPE_CHECKING:
    from . import (
        _screenshot,
        base,
        compiler,
        embed,
        shared_tailwind,
        sitemap,
        tailwind_v3,
        tailwind_v4,
    )
    from ._screenshot import ScreenshotPlugin as _ScreenshotPlugin
    from .base import (
        CommonContext,
        Plugin,
        PostBuildContext,
        PostCompileContext,
        PreCompileContext,
        RegisterRouteContext,
        get_plugin,
    )
    from .compiler import (
        BaseContext,
        CompileContext,
        CompilerHooks,
        ComponentAndChildren,
        PageContext,
        PageDefinition,
    )
    from .embed import EmbedPlugin
    from .sitemap import SitemapPlugin
    from .tailwind_v3 import TailwindV3Plugin
    from .tailwind_v4 import TailwindV4Plugin

    __all__ = [
        "BaseContext",
        "CommonContext",
        "CompileContext",
        "CompilerHooks",
        "ComponentAndChildren",
        "EmbedPlugin",
        "PageContext",
        "PageDefinition",
        "Plugin",
        "PostBuildContext",
        "PostCompileContext",
        "PreCompileContext",
        "RegisterRouteContext",
        "SitemapPlugin",
        "TailwindV3Plugin",
        "TailwindV4Plugin",
        "_ScreenshotPlugin",
        "embed",
        "get_plugin",
        "sitemap",
        "tailwind_v3",
        "tailwind_v4",
    ]

_SUBMODULES: set[str] = {
    "_screenshot",
    "base",
    "compiler",
    "embed",
    "shared_tailwind",
    "sitemap",
    "tailwind_v3",
    "tailwind_v4",
}

_SUBMOD_ATTRS: lazy_loader.SubmodAttrsType = {
    "_screenshot": [("ScreenshotPlugin", "_ScreenshotPlugin")],
    "base": [
        "CommonContext",
        "Plugin",
        "PostBuildContext",
        "PostCompileContext",
        "PreCompileContext",
        "RegisterRouteContext",
        "get_plugin",
    ],
    "compiler": [
        "BaseContext",
        "CompileContext",
        "CompilerHooks",
        "ComponentAndChildren",
        "PageContext",
        "PageDefinition",
    ],
    "embed": ["EmbedPlugin"],
    "sitemap": ["SitemapPlugin"],
    "tailwind_v3": ["TailwindV3Plugin"],
    "tailwind_v4": ["TailwindV4Plugin"],
}

if not TYPE_CHECKING:
    __getattr__, __dir__, _lazy_all = lazy_loader.attach(
        __name__,
        submodules=_SUBMODULES,
        submod_attrs=_SUBMOD_ATTRS,
    )
    __all__ = [
        name
        for name in _lazy_all
        if name not in {"_screenshot", "base", "compiler", "shared_tailwind"}
    ]
