"""Compiler plugins for sites built with ``reflex-site-shared``."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path
from typing import Any

from reflex_base.config import get_config
from reflex_base.plugins import Plugin

from reflex.constants import Dirs
from reflex_site_shared.docs import DocsPage, DocsSiteConfig, discover_docs

_SOURCE_DIR = Path(__file__).parent / "styles" / "assets"
_OUTPUT_DIR = Path("styles") / "reflex-site-shared"
_BASE_STYLESHEETS = ("custom-colors.css", "tailwind-theme.css")
_FONT_STYLESHEET = "fonts.css"
_PUBLIC_ASSETS = ("components/GradientButton.tsx", "icons/search.svg")


def _markdown_asset_path(page: DocsPage) -> Path:
    """Return the public Markdown path corresponding to a docs route.

    Args:
        page: Discovered documentation page.

    Returns:
        The route-relative Markdown asset path.
    """
    route = page.route.strip("/")
    if page.relative_path.stem.lower() == "index":
        return Path(route) / "index.md" if route else Path("index.md")
    return Path(f"{route}.md")


def _trailing_slash_markdown_path(page: DocsPage) -> Path:
    """Return the asset path serving a route's trailing-slash Markdown URL.

    Args:
        page: Discovered documentation page.

    Returns:
        The route-relative ``.md`` alias path.
    """
    route = page.route.strip("/")
    return Path(route) / ".md" if route else Path(".md")


@dataclasses.dataclass(frozen=True, slots=True)
class DocsMarkdownPlugin(Plugin):
    """Publish discovered documentation pages as Markdown assets.

    The generated files mirror the official Reflex docs behavior: ``page.md``
    and ``page/.md`` contain the same source Markdown. An index page is also
    available as ``index.md``.

    Args:
        docs: Content discovery configuration shared with ``register_docs``.
    """

    docs: DocsSiteConfig

    def get_static_assets(self, **context: Any) -> tuple[tuple[Path, str], ...]:
        """Emit route-level Markdown files under the configured frontend path.

        Args:
            context: Compiler plugin context.

        Returns:
            Output paths paired with their source Markdown.
        """
        root = Path(Dirs.PUBLIC)
        if frontend_path := get_config().frontend_path:
            root /= frontend_path.lstrip("/")

        assets: list[tuple[Path, str]] = []
        for page in discover_docs(self.docs):
            content = page.source_path.read_text(encoding="utf-8")
            assets.extend((
                (root / _markdown_asset_path(page), content),
                (root / _trailing_slash_markdown_path(page), content),
            ))
        return tuple(assets)

    def post_build(self, **context: Any) -> None:
        """Stage Markdown for the framework's frontend-path relocation.

        Args:
            context: Post-build plugin context containing ``static_dir``.
        """
        frontend_path = get_config().frontend_path.strip("/")
        if not frontend_path:
            return

        static_dir = Path(context["static_dir"])
        source_root = static_dir / frontend_path
        for page in discover_docs(self.docs):
            for asset_path in (
                _markdown_asset_path(page),
                _trailing_slash_markdown_path(page),
            ):
                destination = static_dir / asset_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_root / asset_path, destination)


@dataclasses.dataclass(frozen=True, slots=True)
class SharedSiteStylesPlugin(Plugin):
    """Inject the shared global CSS and optional Fontsource declarations.

    Args:
        include_fonts: Whether to emit the shared Fontsource declarations.
            Consumers install the referenced Fontsource packages through
            ``rx.Config.frontend_packages``. Existing sites with their own
            font CSS can disable this while retaining the shared theme CSS.
    """

    include_fonts: bool = True

    def get_static_assets(self, **context: Any) -> tuple[tuple[Path, str], ...]:
        """Emit package-owned CSS into the generated web styles directory.

        Args:
            context: Compiler plugin context.

        Returns:
            Output paths paired with their CSS source.
        """
        stylesheets = (
            *_BASE_STYLESHEETS,
            *((_FONT_STYLESHEET,) if self.include_fonts else ()),
        )
        stylesheet_assets = tuple(
            (
                _OUTPUT_DIR / stylesheet,
                (_SOURCE_DIR / stylesheet).read_text(encoding="utf-8"),
            )
            for stylesheet in stylesheets
        )
        public_assets = tuple(
            (
                Path("public") / asset,
                (_SOURCE_DIR / asset).read_text(encoding="utf-8"),
            )
            for asset in _PUBLIC_ASSETS
        )
        return (*stylesheet_assets, *public_assets)

    def get_stylesheet_paths(self, **context: Any) -> tuple[str, ...]:
        """Return imports for Fontsource and generated shared CSS.

        Args:
            context: Compiler plugin context.

        Returns:
            Stylesheet imports in dependency order.
        """
        shared_stylesheets = (
            *_BASE_STYLESHEETS,
            *((_FONT_STYLESHEET,) if self.include_fonts else ()),
        )
        return tuple(f"./reflex-site-shared/{name}" for name in shared_stylesheets)


__all__ = ["DocsMarkdownPlugin", "SharedSiteStylesPlugin"]
