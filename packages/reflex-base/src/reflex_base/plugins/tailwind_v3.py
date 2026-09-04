"""Base class for all plugins."""

import dataclasses
from pathlib import Path
from types import SimpleNamespace

from reflex_base.constants.base import Dirs
from reflex_base.constants.compiler import Ext, PageNames
from reflex_base.plugins.shared_tailwind import (
    TailwindConfig,
    TailwindPlugin,
    tailwind_config_js_template,
)


class Constants(SimpleNamespace):
    """Tailwind constants."""

    # The Tailwindcss version
    VERSION = "tailwindcss@3.4.19"
    # The Tailwind config.
    CONFIG = "tailwind.config.js"
    # Default Tailwind content paths
    CONTENT = [f"./{Dirs.PAGES}/**/*.{{js,ts,jsx,tsx}}", "./utils/**/*.{js,ts,jsx,tsx}"]
    # Relative tailwind style path to root stylesheet in Dirs.STYLES.
    ROOT_STYLE_PATH = "./tailwind.css"

    # Content of the style content.
    ROOT_STYLE_CONTENT = """
@import "tailwindcss/base";

{radix_import}

@tailwind components;
@tailwind utilities;
"""

    # The default tailwind css.
    TAILWIND_CSS = "@import url('./tailwind.css');"


def compile_config(config: TailwindConfig):
    """Compile the Tailwind config.

    Args:
        config: The Tailwind config.

    Returns:
        The compiled Tailwind config.
    """
    return Constants.CONFIG, tailwind_config_js_template(
        **config,
        default_content=Constants.CONTENT,
    )


def compile_root_style(include_radix_themes: bool = True):
    """Compile the Tailwind root style.

    Args:
        include_radix_themes: Whether to include the Radix stylesheet import.

    Returns:
        The compiled Tailwind root style.
    """
    from reflex.compiler.compiler import RADIX_THEMES_STYLESHEET

    return str(
        Path(Dirs.STYLES) / Constants.ROOT_STYLE_PATH
    ), Constants.ROOT_STYLE_CONTENT.format(
        radix_import=(
            f"@import url('{RADIX_THEMES_STYLESHEET}');" if include_radix_themes else ""
        ),
    )


def _index_of_element_that_has(haystack: list[str], needle: str) -> int | None:
    return next(
        (i for i, line in enumerate(haystack) if needle in line),
        None,
    )


def add_tailwind_to_postcss_config(postcss_file_content: str) -> str:
    """Add tailwind to the postcss config.

    Args:
        postcss_file_content: The content of the postcss config file.

    Returns:
        The modified postcss config file content.
    """
    from reflex_base.constants import Dirs

    postcss_file_lines = postcss_file_content.splitlines()

    if _index_of_element_that_has(postcss_file_lines, "tailwindcss") is not None:
        return postcss_file_content

    line_with_postcss_plugins = _index_of_element_that_has(
        postcss_file_lines, "plugins"
    )
    if not line_with_postcss_plugins:
        print(  # noqa: T201
            f"Could not find line with 'plugins' in {Dirs.POSTCSS_JS}. "
            "Please make sure the file exists and is valid."
        )
        return postcss_file_content

    postcss_import_line = _index_of_element_that_has(
        postcss_file_lines, '"postcss-import"'
    )
    postcss_file_lines.insert(
        (postcss_import_line or line_with_postcss_plugins) + 1, "tailwindcss: {},"
    )

    return "\n".join(postcss_file_lines)


def add_tailwind_to_css_file(
    css_file_content: str, *, include_radix_themes: bool = True
) -> str:
    """Add tailwind to the css file.

    Args:
        css_file_content: The content of the css file.
        include_radix_themes: Whether the root stylesheet already imports Radix.

    Returns:
        The modified css file content.
    """
    from reflex.compiler.compiler import RADIX_THEMES_STYLESHEET

    if Constants.TAILWIND_CSS.splitlines()[0] in css_file_content:
        return css_file_content
    if include_radix_themes and RADIX_THEMES_STYLESHEET in css_file_content:
        return css_file_content.replace(
            f"@import url('{RADIX_THEMES_STYLESHEET}');",
            Constants.TAILWIND_CSS,
        )

    lines = css_file_content.splitlines()
    insert_at = next(
        (
            index + 1
            for index, line in enumerate(lines)
            if "__reflex_style_reset.css" in line
        ),
        1,
    )
    lines.insert(insert_at, Constants.TAILWIND_CSS)
    return "\n".join(lines)


@dataclasses.dataclass
class TailwindV3Plugin(TailwindPlugin):
    """Plugin for Tailwind CSS."""

    def get_frontend_development_dependencies(self, **context) -> list[str]:
        """Get the packages required by the plugin.

        Args:
            **context: The context for the plugin.

        Returns:
            A list of packages required by the plugin.
        """
        return [
            *super().get_frontend_development_dependencies(**context),
            Constants.VERSION,
        ]

    def pre_compile(self, **context):
        """Pre-compile the plugin.

        Args:
            context: The context for the plugin.
        """
        context["add_save_task"](compile_config, self.get_unversioned_config())
        include_radix_themes = context["radix_themes_plugin"].enabled

        context["add_save_task"](compile_root_style, include_radix_themes)
        context["add_modify_task"](Dirs.POSTCSS_JS, add_tailwind_to_postcss_config)
        context["add_modify_task"](
            str(Path(Dirs.STYLES) / (PageNames.STYLESHEET_ROOT + Ext.CSS)),
            lambda content: add_tailwind_to_css_file(
                content,
                include_radix_themes=include_radix_themes,
            ),
        )
