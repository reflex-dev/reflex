"""Tailwind CSS configuration types for Reflex plugins."""

import dataclasses
from typing import Any, Literal, TypedDict

from typing_extensions import NotRequired

from reflex.utils.decorator import once

from .base import Plugin as PluginBase

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
import { {{ imp.name }} } from {{ imp.from | tojson }};
{%- endfor %}

{%- for plugin in plugins %}
{% if plugin is mapping and plugin.call is not defined %}
import plugin{{ loop.index }} from {{ plugin.name | tojson }};
{%- elif plugin is not mapping %}
import plugin{{ loop.index }} from {{ plugin | tojson }};
{%- endif %}
{%- endfor %}

{%- for preset in presets %}
import preset{{ loop.index }} from {{ preset | tojson }};
{%- endfor %}

export default {
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
            preset{{ loop.index }},
        {% endfor %}
    ],
    {% endif %}
    plugins: [
        {% for plugin in plugins %}
            {% if plugin is mapping and plugin.call is defined %}
                {{ plugin.call }}(
                    {%- if plugin.args is defined -%}
                        {{ plugin.args | tojson }}
                    {%- endif -%}
                ),
            {% else %}
                plugin{{ loop.index }},
            {% endif %}
        {% endfor %}
    ]
};
"""

    return from_string(source)


@dataclasses.dataclass
class TailwindPlugin(PluginBase):
    """Plugin for Tailwind CSS."""

    config: TailwindConfig = dataclasses.field(
        default_factory=lambda: TailwindConfig(
            plugins=[
                "@tailwindcss/typography",
            ],
        )
    )

    def get_config(self) -> TailwindConfig:
        """Get the Tailwind CSS configuration.

        Returns:
            The Tailwind CSS configuration.
        """
        from reflex.config import get_config

        rxconfig_config = getattr(get_config(), "tailwind", None)

        if rxconfig_config is not None and rxconfig_config != self.config:
            from reflex.utils import console

            console.warn(
                "It seems you have provided a tailwind configuration in your call to `rx.Config`."
                f" You should provide the configuration as an argument to `rx.plugins.{self.__class__.__name__}()` instead."
            )
            return rxconfig_config

        return self.config
