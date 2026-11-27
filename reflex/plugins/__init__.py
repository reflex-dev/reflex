"""Re-export from reflex_base.plugins."""

from typing import TYPE_CHECKING

from reflex_base.plugins import (
    BaseContext,
    CommonContext,
    CompileContext,
    CompilerHooks,
    ComponentAndChildren,
    EmbedPlugin,
    PageContext,
    Plugin,
    PreCompileContext,
    RegisterRouteContext,
    SitemapPlugin,
    TailwindV3Plugin,
    TailwindV4Plugin,
    VitePluginEntry,
    _ScreenshotPlugin,
    embed,
    get_plugin,
    sitemap,
    tailwind_v3,
    tailwind_v4,
)
from reflex_components_radix.plugin import RadixThemesPlugin

# `UIPlugin` comes from the `ui` extra, which may not be installed: it is
# resolved on first use and stays out of `__all__`, so that a star import does
# not need the extra.
if TYPE_CHECKING:
    from reflex_components_ui.plugin import UIPlugin

__all__ = [
    "BaseContext",
    "CommonContext",
    "CompileContext",
    "CompilerHooks",
    "ComponentAndChildren",
    "EmbedPlugin",
    "PageContext",
    "Plugin",
    "PreCompileContext",
    "RadixThemesPlugin",
    "RegisterRouteContext",
    "SitemapPlugin",
    "TailwindV3Plugin",
    "TailwindV4Plugin",
    "VitePluginEntry",
    "_ScreenshotPlugin",
    "embed",
    "get_plugin",
    "sitemap",
    "tailwind_v3",
    "tailwind_v4",
]


def __getattr__(name: str):
    """Resolve `UIPlugin`, which comes from the `ui` extra, on first use.

    Args:
        name: The attribute that was not found in the module.

    Returns:
        The UIPlugin class.

    Raises:
        AttributeError: If the name is not `UIPlugin`.
        ModuleNotFoundError: If the `ui` extra is not installed.
    """
    if name != "UIPlugin":
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    package = "reflex_components_ui"
    try:
        from reflex_components_ui.plugin import UIPlugin
    except ModuleNotFoundError as err:
        if err.name != package:
            raise
        msg = (
            "`rx.plugins.UIPlugin` requires the reflex-components-ui package, "
            "which is not installed. Install it with `pip install 'reflex[ui]'`."
        )
        raise ModuleNotFoundError(msg, name=package) from None
    globals()[name] = UIPlugin
    return UIPlugin
