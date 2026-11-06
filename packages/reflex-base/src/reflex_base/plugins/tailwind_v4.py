"""Tailwind CSS v4 plugin."""

import dataclasses
from typing import ClassVar

from reflex_base.plugins.shared_tailwind import (
    TailwindConfig,
    TailwindConstants,
    TailwindPlugin,
    _index_of_element_that_has,
    add_tailwind_to_css_file,
    compile_config,
    compile_root_style_with,
    tailwind_config_js_template,
)

__all__ = [
    "Constants",
    "TailwindConfig",
    "TailwindPlugin",
    "TailwindV4Plugin",
    "add_tailwind_to_css_file",
    "add_tailwind_to_postcss_config",
    "compile_config",
    "compile_root_style",
    "tailwind_config_js_template",
]

# Held at 4.3.0: 4.3.1+ reworked source-file scanning
# (tailwindlabs/tailwindcss#20214, #20217, #20203) and walks the
# git-ignored `.web` tree, which collapses the docs prod build at scale.
_TAILWIND_VERSION = "4.3.0"


class Constants(TailwindConstants):
    """Tailwind constants."""

    # The Tailwindcss version.
    VERSION = f"tailwindcss@{_TAILWIND_VERSION}"
    # The Tailwind PostCSS plugin, released in lockstep with Tailwind.
    POSTCSS_PLUGIN = f"@tailwindcss/postcss@{_TAILWIND_VERSION}"

    # Content of the style content.
    ROOT_STYLE_CONTENT = """@layer theme, base, components, utilities;
@import "tailwindcss/theme.css" layer(theme);
@import "tailwindcss/preflight.css" layer(base);
{radix_import}@import "tailwindcss/utilities.css" layer(utilities);
@config "../tailwind.config.js";
"""


def compile_root_style(include_radix_themes: bool = True):
    """Compile the Tailwind root style.

    Args:
        include_radix_themes: Whether to include the Radix stylesheet import.

    Returns:
        The compiled Tailwind root style.
    """
    from reflex.compiler.compiler import RADIX_THEMES_STYLESHEET

    return compile_root_style_with(
        Constants.ROOT_STYLE_CONTENT,
        f'@import "{RADIX_THEMES_STYLESHEET}" layer(components);\n',
        include_radix_themes,
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

    line_with_postcss_plugins = _index_of_element_that_has(
        postcss_file_lines, "plugins"
    )
    if not line_with_postcss_plugins:
        print(  # noqa: T201
            f"Could not find line with 'plugins' in {Dirs.POSTCSS_JS}. "
            "Please make sure the file exists and is valid."
        )
        return postcss_file_content

    plugins_to_remove = ['"postcss-import"', "tailwindcss", "autoprefixer"]
    plugins_to_add = ['"@tailwindcss/postcss"']

    for plugin in plugins_to_remove:
        plugin_index = _index_of_element_that_has(postcss_file_lines, plugin)
        if plugin_index is not None:
            postcss_file_lines.pop(plugin_index)

    for plugin in plugins_to_add[::-1]:
        if not _index_of_element_that_has(postcss_file_lines, plugin):
            postcss_file_lines.insert(
                line_with_postcss_plugins + 1, f"  {plugin}: {{}},"
            )

    return "\n".join(postcss_file_lines)


@dataclasses.dataclass
class TailwindV4Plugin(TailwindPlugin):
    """Plugin for Tailwind CSS."""

    _version_packages: ClassVar[tuple[str, ...]] = (
        Constants.VERSION,
        Constants.POSTCSS_PLUGIN,
    )
    _compile_root_style = staticmethod(compile_root_style)
    _add_tailwind_to_postcss_config = staticmethod(add_tailwind_to_postcss_config)
