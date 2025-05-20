"""Base class for all plugins."""

from pathlib import Path
from types import SimpleNamespace

from reflex.constants.base import Dirs
from reflex.plugins.base import Plugin as PluginBase
from reflex.utils.decorator import once


class Constants(SimpleNamespace):
    """Tailwind constants."""

    # The Tailwindcss version
    VERSION = "tailwindcss@4.1.7"
    # The Tailwind config.
    CONFIG = "tailwind.config.js"
    # Default Tailwind content paths
    CONTENT = ["./pages/**/*.{js,ts,jsx,tsx}", "./utils/**/*.{js,ts,jsx,tsx}"]
    # Relative tailwind style path to root stylesheet in Dirs.STYLES.
    ROOT_STYLE_PATH = "./tailwind.css"

    # The default tailwind css.
    TAILWIND_CSS = """
@import "tailwindcss";

@config '../tailwind.config.js';
"""


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


def _compile_tailwind(
    config: dict,
) -> str:
    """Compile the Tailwind config.

    Args:
        config: The Tailwind config.

    Returns:
        The compiled Tailwind config.
    """
    return tailwind_config_js_template().render(
        **config,
    )


def compile_tailwind(
    config: dict,
):
    """Compile the Tailwind config.

    Args:
        config: The Tailwind config.

    Returns:
        The compiled Tailwind config.
    """
    from reflex.utils.prerequisites import get_web_dir

    # Get the path for the output file.
    output_path = str((get_web_dir() / Constants.CONFIG).absolute())

    # Compile the config.
    code = _compile_tailwind(config)
    return output_path, code


def _index_of_element_that_startswith(lines: list[str], prefix: str) -> int | None:
    return next(
        (i for i, line in enumerate(lines) if line.strip().startswith(prefix)),
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

    if _index_of_element_that_startswith(postcss_file_lines, "tailwindcss") is not None:
        return postcss_file_content

    line_with_postcss_plugins = _index_of_element_that_startswith(
        postcss_file_lines, "plugins"
    )
    if not line_with_postcss_plugins:
        print(  # noqa: T201
            f"Could not find line with 'plugins' in {Dirs.POSTCSS_JS}. "
            "Please make sure the file exists and is valid."
        )
        return postcss_file_content

    plugins_to_remove = ['""postcss-import"', "tailwindcss", "autoprefixer"]
    plugins_to_add = ['"@tailwindcss/postcss"']

    for plugin in plugins_to_remove:
        plugin_index = _index_of_element_that_startswith(postcss_file_lines, plugin)
        if plugin_index is not None:
            postcss_file_lines.pop(plugin_index)

    for plugin in plugins_to_add[::-1]:
        postcss_file_lines.insert(line_with_postcss_plugins + 1, f"  {plugin}: {{}},")

    return "\n".join(postcss_file_lines)


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
        ] + [Constants.VERSION, "@tailwindcss/postcss4.1.7"]

    def get_static_assets(self, **context):
        """Get the static assets required by the plugin.

        Args:
            context: The context for the plugin.

        Returns:
            A list of static assets required by the plugin.
        """
        return [(Path("styles/tailwind.css"), Constants.TAILWIND_CSS)]

    def get_stylesheet_paths(self, **context) -> list[str]:
        """Get the paths to the stylesheets required by the plugin relative to the styles directory.

        Args:
            context: The context for the plugin.

        Returns:
            A list of paths to the stylesheets required by the plugin.
        """
        return [Constants.ROOT_STYLE_PATH]

    def pre_compile(self, **context):
        """Pre-compile the plugin.

        Args:
            context: The context for the plugin.
        """
        from reflex.config import get_config

        config = get_config().tailwind or {}

        config["content"] = config.get("content", Constants.CONTENT)
        context["add_save_task"](compile_tailwind, config)
        context["add_modify_task"](Dirs.POSTCSS_JS, add_tailwind_to_postcss_config)
