"""Tailwind CSS configuration types for Reflex plugins."""

import dataclasses
from copy import deepcopy
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


def remove_version_from_plugin(plugin: TailwindPluginConfig) -> TailwindPluginConfig:
    """Remove the version from a plugin name.

    Args:
        plugin: The plugin to remove the version from.

    Returns:
        The plugin without the version.
    """
    from reflex.utils.format import format_library_name

    if isinstance(plugin, str):
        return format_library_name(plugin)

    if plugin_import := plugin.get("import"):
        plugin_import["from"] = format_library_name(plugin_import["from"])

    plugin["name"] = format_library_name(plugin["name"])

    return plugin


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
                "@tailwindcss/typography@0.5.16",
            ],
        )
    )

    def get_frontend_development_dependencies(self, **context) -> list[str]:
        """Get the packages required by the plugin.

        Args:
            **context: The context for the plugin.

        Returns:
            A list of packages required by the plugin.
        """
        config = self.get_config()

        return [
            plugin if isinstance(plugin, str) else plugin.get("name")
            for plugin in config.get("plugins", [])
        ] + config.get("presets", [])

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

    def get_unversioned_config(self) -> TailwindConfig:
        """Get the Tailwind CSS configuration without version-specific adjustments.

        Returns:
            The Tailwind CSS configuration without version-specific adjustments.
        """
        from reflex.utils.format import format_library_name

        config = deepcopy(self.get_config())
        if presets := config.get("presets"):
            # Somehow, having an empty list of presets breaks Tailwind.
            # So we only set the presets if there are any.
            config["presets"] = [format_library_name(preset) for preset in presets]
        config["plugins"] = [
            remove_version_from_plugin(plugin) for plugin in config.get("plugins", [])
        ]
        return config
