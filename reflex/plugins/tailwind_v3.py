"""Base class for all plugins."""

from pathlib import Path
from types import SimpleNamespace

from reflex.constants.base import Dirs
from reflex.constants.compiler import Ext, PageNames
from reflex.plugins.base import Plugin as PluginBase
from reflex.utils.decorator import once


class Constants(SimpleNamespace):
    """Tailwind constants."""

    # The Tailwindcss version
    VERSION = "tailwindcss@3.4.17"
    # The Tailwind config.
    CONFIG = "tailwind.config.js"
    # Default Tailwind content paths
    CONTENT = ["./pages/**/*.{js,ts,jsx,tsx}", "./utils/**/*.{js,ts,jsx,tsx}"]
    # Relative tailwind style path to root stylesheet in Dirs.STYLES.
    ROOT_STYLE_PATH = "./tailwind.css"

    # Content of the style content.
    ROOT_STYLE_CONTENT = """
@import "tailwindcss/base";

@import url('{radix_url}');

@tailwind components;
@tailwind utilities;
"""

    # The default tailwind css.
    TAILWIND_CSS = "@import url('./tailwind.css');"


@once
def tailwind_config_js_template():
    """Get the Tailwind config template.

    Returns:
        The Tailwind config template.
    """
    from reflex.compiler.templates import from_string

    source = r"""
{# Helper macro to render JS objects and arrays #}
{% macro render_js(val, indent=2, level=0) -%}
{%- set space = ' ' * (indent * level) -%}
{%- set next_space = ' ' * (indent * (level + 1)) -%}

{%- if val is mapping -%}
{
{%- for k, v in val.items() %}
{{ next_space }}{{ k if k is string and k.isidentifier() else k|tojson }}: {{ render_js(v, indent, level + 1) }}{{ "," if not loop.last }}
{%- endfor %}
{{ space }}}
{%- elif val is iterable and val is not string -%}
[
{%- for item in val %}
{{ next_space }}{{ render_js(item, indent, level + 1) }}{{ "," if not loop.last }}
{%- endfor %}
{{ space }}]
{%- else -%}
{{ val | tojson }}
{%- endif -%}
{%- endmacro %}

{# Extract destructured imports from plugin dicts only #}
{%- set imports = [] %}
{%- for plugin in plugins if plugin is mapping and plugin.import is defined %}
  {%- set _ = imports.append(plugin.import) %}
{%- endfor %}

/** @type {import('tailwindcss').Config} */
{%- for imp in imports %}
const { {{ imp.name }} } = require({{ imp.from | tojson }});
{%- endfor %}

module.exports = {
  content: {{ render_js(content) }},
  theme: {{ render_js(theme) }},
  {% if darkMode is defined %}darkMode: {{ darkMode | tojson }},{% endif %}
  {% if corePlugins is defined %}corePlugins: {{ render_js(corePlugins) }},{% endif %}
  {% if important is defined %}important: {{ important | tojson }},{% endif %}
  {% if prefix is defined %}prefix: {{ prefix | tojson }},{% endif %}
  {% if separator is defined %}separator: {{ separator | tojson }},{% endif %}
  {% if presets is defined %}
  presets: [
    {% for preset in presets %}
    require({{ preset | tojson }}){{ "," if not loop.last }}
    {% endfor %}
  ],
  {% endif %}
  plugins: [
    {% for plugin in plugins %}
      {% if plugin is mapping %}
        {% if plugin.call is defined %}
          {{ plugin.call }}(
            {%- if plugin.args is defined -%}
              {{ render_js(plugin.args) }}
            {%- endif -%}
          ){{ "," if not loop.last }}
        {% else %}
          require({{ plugin.name | tojson }}){{ "," if not loop.last }}
        {% endif %}
      {% else %}
        require({{ plugin | tojson }}){{ "," if not loop.last }}
      {% endif %}
    {% endfor %}
  ]
};
"""

    return from_string(source)


def compile_config(
    config: dict,
):
    """Compile the Tailwind config.

    Args:
        config: The Tailwind config.

    Returns:
        The compiled Tailwind config.
    """
    return Constants.CONFIG, tailwind_config_js_template().render(
        **config,
    )


def compile_root_style():
    """Compile the Tailwind root style.

    Returns:
        The compiled Tailwind root style.
    """
    from reflex.compiler.compiler import RADIX_THEMES_STYLESHEET

    return str(
        Path(Dirs.STYLES) / Constants.ROOT_STYLE_PATH
    ), Constants.ROOT_STYLE_CONTENT.format(
        radix_url=RADIX_THEMES_STYLESHEET,
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
    from reflex.constants import Dirs

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


def add_tailwind_to_css_file(css_file_content: str) -> str:
    """Add tailwind to the css file.

    Args:
        css_file_content: The content of the css file.

    Returns:
        The modified css file content.
    """
    from reflex.compiler.compiler import RADIX_THEMES_STYLESHEET

    if Constants.TAILWIND_CSS.splitlines()[0] in css_file_content:
        return css_file_content
    if RADIX_THEMES_STYLESHEET not in css_file_content:
        print(  # noqa: T201
            f"Could not find line with '{RADIX_THEMES_STYLESHEET}' in {Dirs.STYLES}. "
            "Please make sure the file exists and is valid."
        )
        return css_file_content
    return css_file_content.replace(
        f"@import url('{RADIX_THEMES_STYLESHEET}');",
        Constants.TAILWIND_CSS,
    )


class Plugin(PluginBase):
    """Plugin for Tailwind CSS."""

    def get_frontend_development_dependencies(self, **context) -> list[str]:
        """Get the packages required by the plugin.

        Args:
            **context: The context for the plugin.

        Returns:
            A list of packages required by the plugin.
        """
        from reflex.config import get_config

        config = get_config()
        return [
            plugin if isinstance(plugin, str) else plugin.get("name")
            for plugin in (config.tailwind or {}).get("plugins", [])
        ] + [Constants.VERSION]

    def pre_compile(self, **context):
        """Pre-compile the plugin.

        Args:
            context: The context for the plugin.
        """
        from reflex.config import get_config

        config = get_config().tailwind or {}

        config["content"] = config.get("content", Constants.CONTENT)
        context["add_save_task"](compile_config, config)
        context["add_save_task"](compile_root_style)
        context["add_modify_task"](Dirs.POSTCSS_JS, add_tailwind_to_postcss_config)
        context["add_modify_task"](
            str(Path(Dirs.STYLES) / (PageNames.STYLESHEET_ROOT + Ext.CSS)),
            add_tailwind_to_css_file,
        )

    def __repr__(self):
        """Return a string representation of the plugin.

        Returns:
            A string representation of the plugin.
        """
        return "TailwindV3Plugin()"
