"""Tailwind CSS configuration types for Reflex plugins."""

import dataclasses
from copy import deepcopy
from typing import Any, Literal, TypedDict, Unpack

from typing_extensions import NotRequired

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


def tailwind_config_js_template(
    *, default_content: list[str], **kwargs: Unpack[TailwindConfig]
):
    """Get the Tailwind config template.

    Args:
        default_content: The default content to use if none is provided.
        **kwargs: The template variables.

    Returns:
        The Tailwind config template.
    """
    import json

    # Extract parameters
    plugins = kwargs.get("plugins", [])
    presets = kwargs.get("presets", [])
    content = kwargs.get("content")
    theme = kwargs.get("theme")
    dark_mode = kwargs.get("darkMode")
    core_plugins = kwargs.get("corePlugins")
    important = kwargs.get("important")
    prefix = kwargs.get("prefix")
    separator = kwargs.get("separator")

    # Extract destructured imports from plugin dicts only
    imports = [
        plugin["import"]
        for plugin in plugins
        if isinstance(plugin, dict) and "import" in plugin
    ]

    # Generate import statements for destructured imports
    import_lines = [
        f"import {{ {imp['name']} }} from {json.dumps(imp['from'])};" for imp in imports
    ]

    # Generate plugin imports
    plugin_imports = []
    for i, plugin in enumerate(plugins, 1):
        if isinstance(plugin, dict) and "call" not in plugin:
            plugin_imports.append(
                f"import plugin{i} from {json.dumps(plugin['name'])};"
            )
        elif not isinstance(plugin, dict):
            plugin_imports.append(f"import plugin{i} from {json.dumps(plugin)};")

    # Generate preset imports
    preset_imports = [
        f"import preset{i} from {json.dumps(preset)};"
        for i, preset in enumerate(presets, 1)
    ]

    # Generate preset array
    preset_array = ""
    if presets:
        preset_list = [f"        preset{i}," for i in range(1, len(presets) + 1)]
        preset_array = f"""    presets: [
{chr(10).join(preset_list)}
    ],"""

    # Generate plugin array
    plugin_list = []
    for i, plugin in enumerate(plugins, 1):
        if isinstance(plugin, dict) and "call" in plugin:
            args_part = ""
            if "args" in plugin:
                args_part = json.dumps(plugin["args"])
            plugin_list.append(f"        {plugin['call']}({args_part}),")
        else:
            plugin_list.append(f"        plugin{i},")

    # Build the config
    all_imports = import_lines + plugin_imports + preset_imports
    imports_section = "\n".join(all_imports)
    if imports_section:
        imports_section += "\n"

    content_value = json.dumps(content if content is not None else default_content)
    theme_part = f"theme: {json.dumps(theme)}," if theme is not None else "theme: {},"
    dark_mode_part = (
        f"    darkMode: {json.dumps(dark_mode)}," if dark_mode is not None else ""
    )
    core_plugins_part = (
        f"    corePlugins: {json.dumps(core_plugins)},"
        if core_plugins is not None
        else ""
    )
    important_part = (
        f"    important: {json.dumps(important)}," if important is not None else ""
    )
    prefix_part = f"    prefix: {json.dumps(prefix)}," if prefix is not None else ""
    separator_part = (
        f"    separator: {json.dumps(separator)}," if separator is not None else ""
    )

    plugins_section = "\n".join(plugin_list)

    config_parts = [
        f"    content: {content_value},",
        f"    {theme_part}",
        dark_mode_part,
        core_plugins_part,
        important_part,
        prefix_part,
        separator_part,
        preset_array,
        f"    plugins: [\n{plugins_section}\n    ]",
    ]

    config_body = "\n".join(part for part in config_parts if part.strip())

    return f"""{imports_section}export default {{
{config_body}
}};"""


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
