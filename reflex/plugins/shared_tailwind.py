"""Tailwind CSS configuration types for Reflex plugins."""

from typing import Any, Literal, NotRequired, TypedDict

from reflex.utils.decorator import once

TailwindPluginImport = TypedDict(
    "TailwindPluginImport",
    {
        "name": str,
        "from": str,
    },
)

TailwindPluginWithCallConfig = TypedDict(
    "TailwindPluginWithCallConfig",
    {
        "name": str,
        "import": NotRequired[TailwindPluginImport],
        "call": str,
        "args": NotRequired[dict[str, Any]],
    },
)

TailwindPluginWithoutCallConfig = TypedDict(
    "TailwindPluginWithoutCallConfig",
    {
        "name": str,
        "import": NotRequired[TailwindPluginImport],
    },
)

TailwindPluginConfig = (
    TailwindPluginWithCallConfig | TailwindPluginWithoutCallConfig | str
)


class TailwindConfig(TypedDict):
    """Tailwind CSS configuration options.

    See: https://tailwindcss.com/docs/configuration
    """

    content: NotRequired[list[str]]
    important: NotRequired[str | bool]
    prefix: NotRequired[str]
    separator: NotRequired[str]
    presets: NotRequired[list[str]]
    darkMode: NotRequired[Literal["media", "class", "selector"]]
    theme: NotRequired[dict[str, Any]]
    corePlugins: NotRequired[list[str] | dict[str, bool]]
    plugins: NotRequired[list[TailwindPluginConfig]]


@once
def tailwind_config_js_template():
    """Get the Tailwind config template.

    Returns:
        The Tailwind config template.
    """
    from reflex.compiler.templates import from_string

    source = r"""
{# Extract destructured imports from plugin dicts only #}
{%- set imports = [] %}

{%- for plugin in plugins if plugin is mapping and plugin.import is defined %}
  {%- set _ = imports.append(plugin.import) %}
{%- endfor %}

{%- for imp in imports %}
const { {{ imp.name }} } = require({{ imp.from | tojson }});
{%- endfor %}

module.exports = {
  content: {{ (content if content is defined else DEFAULT_CONTENT) | tojson }},
  {% if theme is defined %}theme: {{ theme | tojson }},{% else %}theme: {},{% endif %}
  {% if darkMode is defined %}darkMode: {{ darkMode | tojson }},{% endif %}
  {% if corePlugins is defined %}corePlugins: {{ corePlugins | tojson }},{% endif %}
  {% if important is defined %}important: {{ important | tojson }},{% endif %}
  {% if prefix is defined %}prefix: {{ prefix | tojson }},{% endif %}
  {% if separator is defined %}separator: {{ separator | tojson }},{% endif %}
  {% if presets is defined %}
  presets: [
    {% for preset in presets %}
        require({{ preset | tojson }}),
    {% endfor %}
  ],
  {% endif %}
  plugins: [
    {% for plugin in plugins %}
        {% if plugin is mapping %}
            {% if plugin.call is defined %}
                {{ plugin.call }}(
                    {%- if plugin.args is defined -%}
                        {{ plugin.args | tojson }}
                    {%- endif -%}
                ),
            {% else %}
                require({{ plugin.name | tojson }}),
            {% endif %}
        {% else %}
            require({{ plugin | tojson }}),
        {% endif %}
    {% endfor %}
  ]
};
"""

    return from_string(source)
