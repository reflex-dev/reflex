"""Plugin support for opt-in Radix Themes integration."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from reflex_base.components.component import BaseComponent, Component
from reflex_base.components.dynamic import bundle_library
from reflex_base.plugins.base import Plugin
from reflex_base.utils import console

from reflex_components_radix import themes
from reflex_components_radix.themes.base import RadixThemesComponent

if TYPE_CHECKING:
    from reflex_base.plugins.compiler import PageContext


RADIX_THEMES_STYLESHEET = "@radix-ui/themes/styles.css"
RADIX_THEMES_PACKAGE = "@radix-ui/themes@3.3.0"
_DEPRECATION_VERSION = "0.9.0"
_REMOVAL_VERSION = "1.0"


@dataclasses.dataclass
class RadixThemesPlugin(Plugin):
    """Opt-in plugin for Radix Themes assets and app-level wrapping."""

    theme: Component | None = dataclasses.field(
        default_factory=lambda: themes.theme(accent_color="blue")
    )
    enabled: bool = dataclasses.field(default=True, repr=False)
    _explicit: bool = dataclasses.field(default=True, repr=False)
    _app_theme_warning_emitted: bool = dataclasses.field(
        default=False, init=False, repr=False
    )

    @classmethod
    def create_implicit(cls) -> RadixThemesPlugin:
        """Create a compile-local plugin that starts disabled.

        Returns:
            The disabled compile-local plugin.
        """
        return cls(enabled=False, _explicit=False)

    def get_stylesheet_paths(self, **context: Any) -> tuple[str, ...]:
        """Return the Radix Themes stylesheet when enabled."""
        return (RADIX_THEMES_STYLESHEET,) if self.enabled else ()

    def get_frontend_dependencies(self, **context: Any) -> tuple[str, ...]:
        """Return the Radix Themes package when enabled."""
        return (RADIX_THEMES_PACKAGE,) if self.enabled else ()

    def enter_component(
        self,
        comp: BaseComponent,
        /,
        *,
        page_context: PageContext,
        compile_context: Any,
        in_prop_tree: bool = False,
    ) -> None:
        """Auto-enable the plugin when a Radix Themes component is compiled."""
        if self.enabled or not isinstance(comp, RadixThemesComponent):
            return

        self.enabled = True
        bundle_library(RADIX_THEMES_PACKAGE)
        if not self._explicit and not self._app_theme_warning_emitted:
            console.deprecate(
                feature_name="Implicit Radix Themes enablement",
                reason=(
                    "a Radix Themes component was detected, which enables the full "
                    "Radix CSS bundle. Configure `rx.plugins.RadixThemesPlugin()` in "
                    "`rxconfig.py` to make this explicit, or remove Radix components "
                    "to avoid loading the stylesheet"
                ),
                deprecation_version=_DEPRECATION_VERSION,
                removal_version=_REMOVAL_VERSION,
            )

    def compile_page(
        self,
        page_ctx: PageContext,
        /,
        **kwargs: Any,
    ) -> None:
        """Inject the app-level theme wrapper when Radix Themes is active."""
        if self.enabled and self.theme is not None:
            page_ctx.app_wrap_components[20, "Theme"] = self.theme

    def get_theme(self) -> Component | None:
        """Return the effective theme component for the active compile."""
        return self.theme if self.enabled else None

    def apply_app_theme(self, theme: Component) -> None:
        """Handle deprecated ``App(theme=...)`` compatibility."""
        console.deprecate(
            feature_name="App(theme=...)",
            reason=(
                "configure `rx.plugins.RadixThemesPlugin(theme=...)` in "
                "`rxconfig.py` instead"
            ),
            deprecation_version=_DEPRECATION_VERSION,
            removal_version=_REMOVAL_VERSION,
        )
        self._app_theme_warning_emitted = True

        if self._explicit:
            return

        self.enabled = True
        self.theme = theme
