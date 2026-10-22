"""Tailwind CSS configuration types and helpers shared by the Tailwind plugins."""

import dataclasses
import logging
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, Literal, NotRequired, TypedDict

from typing_extensions import Unpack

from reflex_base.constants.base import Dirs
from reflex_base.constants.compiler import Ext, PageNames

from .base import Plugin as PluginBase

logger = logging.getLogger(__name__)


class TailwindConstants(SimpleNamespace):
    """Tailwind constants shared by every Tailwind version."""

    # The Tailwind config.
    CONFIG = "tailwind.config.js"
    # Default Tailwind content paths
    CONTENT = [f"./{Dirs.PAGES}/**/*.{{js,ts,jsx,tsx}}", "./utils/**/*.{js,ts,jsx,tsx}"]
    # Relative tailwind style path to root stylesheet in Dirs.STYLES.
    ROOT_STYLE_PATH = "./tailwind.css"
    # The default tailwind css.
    TAILWIND_CSS = "@import url('./tailwind.css');"


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
    from reflex_base.utils.format import format_library_name

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
    """Generate a Tailwind CSS configuration file in JavaScript format.

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
        if isinstance(plugin, Mapping) and "import" in plugin
    ]

    # Generate import statements for destructured imports
    import_lines = "\n".join([
        f"import {{ {imp['name']} }} from {json.dumps(imp['from'])};" for imp in imports
    ])

    # Generate plugin imports
    plugin_imports = []
    for i, plugin in enumerate(plugins, 1):
        if isinstance(plugin, Mapping) and "call" not in plugin:
            plugin_imports.append(
                f"import plugin{i} from {json.dumps(plugin['name'])};"
            )
        elif not isinstance(plugin, Mapping):
            plugin_imports.append(f"import plugin{i} from {json.dumps(plugin)};")

    plugin_imports_lines = "\n".join(plugin_imports)

    presets_imports_lines = "\n".join([
        f"import preset{i} from {json.dumps(preset)};"
        for i, preset in enumerate(presets, 1)
    ])

    # Generate plugin array
    plugin_list = []
    for i, plugin in enumerate(plugins, 1):
        if isinstance(plugin, Mapping) and "call" in plugin:
            args_part = ""
            if "args" in plugin:
                args_part = json.dumps(plugin["args"])
            plugin_list.append(f"{plugin['call']}({args_part})")
        else:
            plugin_list.append(f"plugin{i}")

    plugin_use_str = ",".join(plugin_list)

    return rf"""
{import_lines}

{plugin_imports_lines}

{presets_imports_lines}

export default {{
    content: {json.dumps(content or default_content)},
    theme: {json.dumps(theme or {})},
    {f"darkMode: {json.dumps(dark_mode)}," if dark_mode is not None else ""}
    {f"corePlugins: {json.dumps(core_plugins)}," if core_plugins is not None else ""}
    {f"important: {json.dumps(important)}," if important is not None else ""}
    {f"prefix: {json.dumps(prefix)}," if prefix is not None else ""}
    {f"separator: {json.dumps(separator)}," if separator is not None else ""}
    {f"presets: [{', '.join(f'preset{i}' for i in range(1, len(presets) + 1))}]," if presets else ""}
    plugins: [{plugin_use_str}]
}};
"""


def compile_config(config: TailwindConfig):
    """Compile the Tailwind config.

    Args:
        config: The Tailwind config.

    Returns:
        The compiled Tailwind config.
    """
    return TailwindConstants.CONFIG, tailwind_config_js_template(
        **config,
        default_content=TailwindConstants.CONTENT,
    )


def compile_root_style_with(
    template: str, radix_import: str, include_radix_themes: bool
) -> tuple[str, str]:
    """Compile a Tailwind root style from a version-specific template.

    Args:
        template: The root style template with a `{radix_import}` placeholder.
        radix_import: The Radix stylesheet import line for this Tailwind version.
        include_radix_themes: Whether to include the Radix stylesheet import.

    Returns:
        The root style path and the compiled root style.
    """
    return str(Path(Dirs.STYLES) / TailwindConstants.ROOT_STYLE_PATH), template.format(
        radix_import=radix_import if include_radix_themes else ""
    )


def _index_of_element_that_has(haystack: list[str], needle: str) -> int | None:
    return next(
        (i for i, line in enumerate(haystack) if needle in line),
        None,
    )


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

    if TailwindConstants.TAILWIND_CSS.splitlines()[0] in css_file_content:
        return css_file_content
    if include_radix_themes and RADIX_THEMES_STYLESHEET in css_file_content:
        return css_file_content.replace(
            f"@import url('{RADIX_THEMES_STYLESHEET}');",
            TailwindConstants.TAILWIND_CSS,
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
    lines.insert(insert_at, TailwindConstants.TAILWIND_CSS)
    return "\n".join(lines)


@dataclasses.dataclass
class TailwindPlugin(PluginBase):
    """Plugin for Tailwind CSS."""

    config: TailwindConfig = dataclasses.field(
        default_factory=lambda: TailwindConfig(
            plugins=[
                "@tailwindcss/typography@0.5.20",
            ],
        )
    )

    _version_packages: ClassVar[tuple[str, ...]] = ()

    @staticmethod
    def _compile_root_style(include_radix_themes: bool = True) -> tuple[str, str]:
        """Compile the root style for this Tailwind version.

        Args:
            include_radix_themes: Whether to include the Radix stylesheet import.

        Raises:
            NotImplementedError: Tailwind version plugins must override this.
        """
        raise NotImplementedError

    @staticmethod
    def _add_tailwind_to_postcss_config(postcss_file_content: str) -> str:
        """Add this Tailwind version to the postcss config.

        Args:
            postcss_file_content: The content of the postcss config file.

        Raises:
            NotImplementedError: Tailwind version plugins must override this.
        """
        raise NotImplementedError

    def get_frontend_development_dependencies(self, **context) -> list[str]:
        """Get the packages required by the plugin.

        Args:
            **context: The context for the plugin.

        Returns:
            A list of packages required by the plugin.
        """
        config = self.get_config()

        return [
            *(
                plugin if isinstance(plugin, str) else plugin.get("name")
                for plugin in config.get("plugins", [])
            ),
            *config.get("presets", []),
            *self._version_packages,
        ]

    def pre_compile(self, **context):
        """Pre-compile the plugin.

        Args:
            context: The context for the plugin.
        """
        context["add_save_task"](compile_config, self.get_unversioned_config())
        include_radix_themes = context["radix_themes_plugin"].enabled

        context["add_save_task"](self._compile_root_style, include_radix_themes)
        context["add_modify_task"](
            Dirs.POSTCSS_JS, self._add_tailwind_to_postcss_config
        )
        context["add_modify_task"](
            str(Path(Dirs.STYLES) / (PageNames.STYLESHEET_ROOT + Ext.CSS)),
            lambda content: add_tailwind_to_css_file(
                content,
                include_radix_themes=include_radix_themes,
            ),
        )

    def get_config(self) -> TailwindConfig:
        """Get the Tailwind CSS configuration.

        Returns:
            The Tailwind CSS configuration.
        """
        from reflex_base.config import get_config

        rxconfig_config = getattr(get_config(), "tailwind", None)

        if rxconfig_config is not None and rxconfig_config != self.config:
            logger.warning(
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
        from reflex_base.utils.format import format_library_name

        config = deepcopy(self.get_config())
        if presets := config.get("presets"):
            # Somehow, having an empty list of presets breaks Tailwind.
            # So we only set the presets if there are any.
            config["presets"] = [format_library_name(preset) for preset in presets]
        config["plugins"] = [
            remove_version_from_plugin(plugin) for plugin in config.get("plugins", [])
        ]
        return config
