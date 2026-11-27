"""The plugin that compiles the styles of the rx.ui components."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path

from reflex_base.constants import Dirs, Ext, PageNames
from reflex_base.plugins import Plugin, VitePluginEntry

from reflex_components_ui.constants import (
    JS_SRC,
    LIGHTNINGCSS_VERSION,
    STYLEX_VERSION,
    WEB_DIR,
)

# Declares the cascade layers, so it comes before any stylesheet that names one.
BASE_STYLESHEET_IMPORT = f"@import url('../{WEB_DIR}/base.css');"

# The cascade layer the styles of the components are compiled into.
CSS_LAYER = "reflex-ui"

_VITE_PLUGIN = VitePluginEntry(
    imports=(
        f'import reflexUIStylex from "./{WEB_DIR}/vite-plugin-stylex.js"',
        'import { Features as lightningcssFeatures } from "lightningcss"',
    ),
    call=f"""reflexUIStylex("{PageNames.STYLESHEET_ROOT}", {{
      useCSSLayers: {{ prefix: "{CSS_LAYER}" }},
      styleResolution: "application-order",
      lightningcssOptions: {{ minify: true, exclude: lightningcssFeatures.LightDark }},
    }})""",
)


def add_base_stylesheet(content: str) -> str:
    """Import the base stylesheet ahead of every other one in the root stylesheet.

    Args:
        content: The root stylesheet.

    Returns:
        The root stylesheet with the import, unchanged when it has it already.
    """
    if BASE_STYLESHEET_IMPORT in content:
        return content
    lines = content.splitlines()
    # After the leading `@layer` statement: one placed between two imports
    # would make the second import invalid.
    first_import = next(
        (index for index, line in enumerate(lines) if line.startswith("@import")),
        len(lines),
    )
    lines.insert(first_import, BASE_STYLESHEET_IMPORT)
    return "\n".join(lines)


@dataclasses.dataclass
class Theme:
    """The look of the rx.ui components across an app. It has no options yet."""


@dataclasses.dataclass
class UIPlugin(Plugin):
    """Compile the styles of the rx.ui components into the app's stylesheet.

    Attributes:
        theme: The look of the components across the app.
    """

    theme: Theme = dataclasses.field(default_factory=Theme)

    def get_frontend_development_dependencies(self, **context) -> list[str]:
        """Get the packages that compile the styles.

        They only run in the build: the compiled pages import none of them.

        Args:
            **context: The context for the plugin.

        Returns:
            The StyleX compiler and its Vite plugin, at their exact versions.
        """
        return [
            f"@stylexjs/stylex@{STYLEX_VERSION}",
            f"@stylexjs/unplugin@{STYLEX_VERSION}",
            f"lightningcss@{LIGHTNINGCSS_VERSION}",
        ]

    def get_static_assets(self, **context) -> Sequence[tuple[Path, str | bytes]]:
        """Get the javascript package, as files of the web directory.

        Args:
            **context: The context for the plugin.

        Returns:
            Every file of the javascript package and where it is written.
        """
        return [
            (WEB_DIR / path.relative_to(JS_SRC), path.read_text(encoding="utf-8"))
            for path in sorted(JS_SRC.rglob("*"))
            if path.is_file()
        ]

    def get_vite_plugins(self, **context) -> Sequence[VitePluginEntry]:
        """Get the Vite plugin that compiles the styles.

        Args:
            **context: The context for the plugin.

        Returns:
            The StyleX plugin, wrapped for the React Router build.
        """
        return [_VITE_PLUGIN]

    def pre_compile(self, **context) -> None:
        """Import the base stylesheet into the root stylesheet.

        Args:
            **context: The context for the plugin.
        """
        context["add_modify_task"](
            str(Path(Dirs.STYLES) / (PageNames.STYLESHEET_ROOT + Ext.CSS)),
            add_base_stylesheet,
        )
