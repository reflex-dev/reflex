"""Plugin support for opt-in Radix Themes integration."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from reflex_base.components.component import BaseComponent, Component
from reflex_base.components.dynamic import bundle_library
from reflex_base.plugins.base import Plugin
from reflex_base.utils import console
from reflex_base.vars.base import get_python_literal

from reflex_components_radix import themes
from reflex_components_radix.themes.base import RadixThemesComponent

if TYPE_CHECKING:
    from reflex_base.plugins.compiler import PageContext


RADIX_THEMES_STYLESHEET = "@radix-ui/themes/styles.css"
RADIX_THEMES_PACKAGE = "@radix-ui/themes@3.3.0"
_DEPRECATION_VERSION = "0.9.0"
_REMOVAL_VERSION = "1.0"

_RADIX_THEMES_TOKENS_BASE = "@radix-ui/themes/tokens/base.css"
_RADIX_THEMES_COMPONENTS = "@radix-ui/themes/components.css"
_RADIX_THEMES_UTILITIES = "@radix-ui/themes/utilities.css"

# Natural accent/gray pairings per https://www.radix-ui.com/themes/docs/theme/color#natural-pairing
_RADIX_ACCENT_TO_AUTO_GRAY: dict[str, str] = {
    "tomato": "mauve",
    "red": "mauve",
    "ruby": "mauve",
    "crimson": "mauve",
    "pink": "mauve",
    "plum": "mauve",
    "purple": "mauve",
    "violet": "mauve",
    "iris": "slate",
    "indigo": "slate",
    "blue": "slate",
    "sky": "slate",
    "cyan": "slate",
    "teal": "sage",
    "jade": "sage",
    "mint": "sage",
    "green": "sage",
    "grass": "sage",
    "orange": "sand",
    "amber": "sand",
    "yellow": "sand",
    "lime": "sand",
    "brown": "sand",
    "bronze": "sand",
    "gold": "sand",
    "gray": "gray",
}

_RADIX_VALID_GRAYS = frozenset({"gray", "mauve", "slate", "sage", "olive", "sand"})


def _radix_color_stylesheet(color: str) -> str:
    """Return the granular CSS import path for a single Radix color scale.

    Args:
        color: The Radix color name (e.g. ``"blue"``, ``"slate"``).

    Returns:
        The Radix Themes CSS path for that color.
    """
    return f"@radix-ui/themes/tokens/colors/{color}.css"


def _resolve_theme_color(
    component: BaseComponent, prop_name: str
) -> tuple[str | None, bool]:
    """Resolve a Theme color prop into either a literal or a dynamic marker.

    Args:
        component: The Theme component being inspected.
        prop_name: The color prop name (``"accent_color"`` or ``"gray_color"``).

    Returns:
        A tuple ``(literal, is_dynamic)``. ``literal`` is the resolved string
        when the prop is set to a static value; ``is_dynamic`` is True only
        when the prop is set but cannot be resolved at compile time.
    """
    raw = getattr(component, prop_name, None)
    if raw is None:
        return None, False
    literal = get_python_literal(raw)
    if isinstance(literal, str):
        return literal, False
    return None, True


def _walk_components(root: BaseComponent) -> Iterable[BaseComponent]:
    """Yield ``root`` and every descendant reachable via ``.children``.

    Args:
        root: The component subtree to walk.

    Yields:
        Each component in the subtree, including ``root`` itself.
    """
    stack: list[BaseComponent] = [root]
    while stack:
        node = stack.pop()
        yield node
        children = getattr(node, "children", None)
        if children:
            stack.extend(children)


def _collect_radix_theme_colors(
    roots: Iterable[BaseComponent | None],
) -> tuple[set[str], set[str], bool]:
    """Walk component trees for Theme components and collect their colors.

    Args:
        roots: Component trees to walk for Theme components.

    Returns:
        A tuple ``(accent_colors, gray_colors, needs_fallback)``.
        ``needs_fallback`` is True if any Theme has a state-driven color
        or an unrecognized color literal -- in either case the caller falls
        back to the monolithic stylesheet, so a typo never resolves to a 404
        ``tokens/colors/<garbage>.css`` import.
    """
    accents: set[str] = set()
    grays: set[str] = set()
    needs_fallback = False
    for root in roots:
        if root is None:
            continue
        for node in _walk_components(root):
            if getattr(node, "tag", None) != "Theme":
                continue
            accent, accent_dynamic = _resolve_theme_color(node, "accent_color")
            gray, gray_dynamic = _resolve_theme_color(node, "gray_color")
            if accent_dynamic or gray_dynamic:
                needs_fallback = True
            if accent is not None and accent not in _RADIX_ACCENT_TO_AUTO_GRAY:
                needs_fallback = True
                continue
            if gray is not None and gray != "auto" and gray not in _RADIX_VALID_GRAYS:
                needs_fallback = True
                continue
            if accent:
                accents.add(accent)
            if gray and gray != "auto":
                grays.add(gray)
            # When gray_color is unset or "auto", Radix pairs the accent with a
            # natural gray scale -- ship that scale too.
            if accent and (gray is None or gray == "auto"):
                grays.add(_RADIX_ACCENT_TO_AUTO_GRAY[accent])
    return accents, grays, needs_fallback


def get_radix_themes_stylesheets(
    roots: Iterable[BaseComponent | None] | None = None,
) -> list[str]:
    """Return the Radix Themes stylesheets to import.

    Importing the granular per-color CSS files (tokens/base.css +
    tokens/colors/<accent>.css + components.css + utilities.css) instead of
    the monolithic ``styles.css`` lets the bundler drop the ~30 unused color
    scales. Falls back to the monolithic stylesheet when ``roots`` is None,
    when no static accent is detected, when any Theme uses a state-driven
    color (so runtime color switches still work), or when a Theme references
    a color name not recognized by the granular file layout (which would
    otherwise resolve to a 404 ``tokens/colors/<garbage>.css``).

    Args:
        roots: Component trees to scan for Theme components.

    Returns:
        Ordered list of stylesheet paths to import.
    """
    if roots is None:
        return [RADIX_THEMES_STYLESHEET]
    accents, grays, needs_fallback = _collect_radix_theme_colors(roots)
    if needs_fallback or not accents:
        return [RADIX_THEMES_STYLESHEET]
    sheets = [_RADIX_THEMES_TOKENS_BASE]
    # An accent and its paired gray can be the same scale (e.g. accent_color="gray"
    # auto-pairs with "gray"); subtract to avoid importing the same file twice.
    sheets.extend(_radix_color_stylesheet(c) for c in sorted(grays - accents))
    sheets.extend(_radix_color_stylesheet(c) for c in sorted(accents))
    sheets.extend([_RADIX_THEMES_COMPONENTS, _RADIX_THEMES_UTILITIES])
    return sheets


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
        """Return the Radix Themes stylesheets when enabled.

        When ``theme_roots`` are supplied via context, only the color scales
        actually referenced by ``Theme`` components are shipped (falling back
        to the monolithic stylesheet when a color is state-driven).
        """
        if not self.enabled:
            return ()
        return tuple(get_radix_themes_stylesheets(context.get("theme_roots")))

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
