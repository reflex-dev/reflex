"""Plugin integrating the Reflex UI component library with the compiler.

The plugin compiles the active :class:`~reflex_components_core.ui.theme.Theme`
into a stylesheet inside the Tailwind CSS graph. It is enabled automatically
when a UI component is compiled; add ``rx.plugins.UIComponentsPlugin()`` to
``rxconfig.py`` to customize the theme.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from reflex_base.components.component import BaseComponent
from reflex_base.plugins.base import Plugin
from reflex_base.utils import console

from reflex_components_core.ui.base import UIComponent, ui_component_created
from reflex_components_core.ui.theme import Theme

if TYPE_CHECKING:
    from reflex_base.plugins.compiler import PageContext

THEME_STYLESHEET_PATH = "styles/reflex-ui/theme.css"
THEME_STYLESHEET_IMPORT = "./reflex-ui/theme.css"


def _tailwind_v4_plugin_active() -> bool:
    """Check whether the Tailwind v4 plugin is configured.

    Returns:
        True if a TailwindV4Plugin instance is in the config plugins.
    """
    from reflex_base.config import get_config
    from reflex_base.plugins.tailwind_v4 import TailwindV4Plugin

    return any(isinstance(plugin, TailwindV4Plugin) for plugin in get_config().plugins)


@dataclasses.dataclass
class UIComponentsPlugin(Plugin):
    """Plugin for theming and stylesheet support of Reflex UI components."""

    theme: Theme = dataclasses.field(default_factory=Theme)
    enabled: bool = dataclasses.field(default=True, repr=False)
    _implicit: bool = dataclasses.field(default=False, repr=False)
    _tailwind_warning_emitted: bool = dataclasses.field(
        default=False, init=False, repr=False
    )

    @classmethod
    def create_implicit(cls) -> UIComponentsPlugin:
        """Create a compile-local plugin that starts disabled.

        Returns:
            The disabled compile-local plugin.
        """
        return cls(enabled=False, _implicit=True)

    def _effective_enabled(self) -> bool:
        """Resolve whether the theme stylesheet should ship.

        An implicit plugin also enables when a UI component was created in
        this process, covering components that never pass through the page
        compiler hooks (e.g. inside ``rx.memo`` or the hydrate fallback).

        Returns:
            Whether the plugin contributes its assets.
        """
        return self.enabled or (self._implicit and ui_component_created())

    def get_stylesheet_paths(self, **context: Any) -> tuple[str, ...]:
        """Return the theme stylesheet import when enabled.

        Args:
            **context: The context for the plugin.

        Returns:
            The stylesheet paths relative to the styles directory.
        """
        return (THEME_STYLESHEET_IMPORT,) if self._effective_enabled() else ()

    def get_static_assets(self, **context: Any) -> tuple[tuple[str, str], ...]:
        """Return the compiled theme stylesheet when enabled.

        Args:
            **context: The context for the plugin.

        Returns:
            Pairs of output path (relative to the web directory) and content.
        """
        if not self._effective_enabled():
            return ()
        return ((THEME_STYLESHEET_PATH, self.theme.stylesheet()),)

    def enter_component(
        self,
        comp: BaseComponent,
        /,
        *,
        page_context: PageContext,
        compile_context: Any,
        in_prop_tree: bool = False,
    ) -> None:
        """Auto-enable the plugin when a UI component is compiled.

        Args:
            comp: The component being compiled.
            page_context: The page compile context.
            compile_context: The app compile context.
            in_prop_tree: Whether the component is inside a prop tree.
        """
        if not isinstance(comp, UIComponent):
            return
        self.enabled = True
        if not self._tailwind_warning_emitted and not _tailwind_v4_plugin_active():
            self._tailwind_warning_emitted = True
            console.warn(
                "rx.ui components are styled with Tailwind CSS, but "
                "rx.plugins.TailwindV4Plugin is not configured. Add it to "
                "`plugins` in `rxconfig.py` for the components to render "
                "with their intended styles."
            )
