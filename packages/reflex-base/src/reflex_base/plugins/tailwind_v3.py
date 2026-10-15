"""Tailwind CSS v3 plugin."""

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
    "TailwindV3Plugin",
    "add_tailwind_to_css_file",
    "add_tailwind_to_postcss_config",
    "compile_config",
    "compile_root_style",
    "tailwind_config_js_template",
]


class Constants(TailwindConstants):
    """Tailwind constants."""

    # The Tailwindcss version
    VERSION = "tailwindcss@3.4.19"

    # Content of the style content.
    ROOT_STYLE_CONTENT = """
@import "tailwindcss/base";

{radix_import}

@tailwind components;
@tailwind utilities;
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
        f"@import url('{RADIX_THEMES_STYLESHEET}');",
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


@dataclasses.dataclass
class TailwindV3Plugin(TailwindPlugin):
    """Plugin for Tailwind CSS."""

    _version_packages: ClassVar[tuple[str, ...]] = (Constants.VERSION,)
    _compile_root_style = staticmethod(compile_root_style)
    _add_tailwind_to_postcss_config = staticmethod(add_tailwind_to_postcss_config)
