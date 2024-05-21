"""Import all classes and functions the end user will need to make an app.

Anything imported here will be available in the default Reflex import as `rx.*`.
To signal to typecheckers that something should be reexported,
we use the Flask "import name as name" syntax.
"""

from __future__ import annotations

import importlib
from typing import Type

from reflex.page import page as page
from reflex.utils import console
from reflex.utils.format import to_snake_case

_ALL_COMPONENTS = [
    "image",
]

_MAPPING = {
    "reflex.experimental": ["_x"],
    "reflex.admin": ["admin", "AdminDash"],
    "reflex.app": ["app", "App", "UploadFile"],
    "reflex.base": ["base", "Base"],
    "reflex.compiler": ["compiler"],
    "reflex.components.component": ["Component", "NoSSRComponent", "memo"],
    "reflex.components.chakra": ["chakra"],
    "reflex.components.el": ["el"],
    "reflex.components.lucide": ["lucide", "icon"],
    "reflex.components.base": [
        "fragment",
        "Fragment",
        "script",
        "Script"
    ],
    "reflex.components.suneditor": [
        "editor",
        "EditorButtonList",
        "EditorOptions",
    ],
    "reflex.components": ["image"],
    "reflex.components.markdown.markdown" : ["markdown"],
    "reflex.components.next": ["next"],
    "reflex.components.radix": ["radix", "color_mode"],
    "reflex.components.radix.themes": ["theme", "theme_panel"],
    "reflex.components.plotly": ["plotly"],
    "reflex.components.react_player": [
        "audio",
        "video"
    ],
    "reflex.components.radix.themes.layout": [
        "box",
        "center",
        "container",
        "flex",
        "grid",
        "section",
        "spacer",
        "stack",
        "hstack",
        "vstack",
        "list",
        "list_item",
        "ordered_list",
        "unordered_list",
    ],
    "reflex.components.core": ["color",
                               "cond",
                               "foreach",
                               "html",
                               "match",
                               "color_mode_cond",
                               "connection_banner",
                               "connection_modal",
                               "debounce_input",
                               "desktop_only",
                               "mobile_and_tablet",
                               "mobile_only",
                               "tablet_and_desktop",
                               "tablet_only",
                               "cancel_upload",
                               "clear_selected_files",
                               "get_upload_dir",
                               "get_upload_url",
                               "selected_files",
                               "upload",
                               ],
    "reflex.components.radix.primitives": [
        "accordion",
        "drawer",
        "form",
        "progress",
        "slider"
    ],
    "reflex.components.radix.themes.components": [
        "alert_dialog",
        "aspect_ratio",
        "avatar",
        "badge",
        "button",
        "callout",
        "card",
        "checkbox",
        "checkbox_cards",
        "checkbox_group",
        "context_menu",
        "data_list",
        "dialog",
        "divider",
        "dropdown_menu",
        "hover_card",
        "icon_button",
        "input",
        "inset",
        "menu",
        "popover",
        "radio",
        "radio_cards",
        "radio_group",
        "scroll_area",
        "segmented_control",
        "select",
        "separator",
        "skeleton",
        "slider",
        "spinner",
        "switch",
        "table",
        "tabs",
        "text_area",
        "text_field",
        "tooltip",
    ],
    "reflex.components.radix.themes.typography": [
        "heading",
        "blockquote",
        "code",
        "link",
        "text",
    ],
    "reflex.components.datadisplay": [
        "code_block",
        "data_editor",
        "data_editor_theme",
        "logo"
    ],
    "reflex.components.recharts": ["recharts"],
    "reflex.components.moment": ["MomentDelta", "moment"],
    "reflex.config": ["config", "Config", "DBConfig"],
    "reflex.constants": ["constants", "Env"],
    "reflex.event": [
        "event",
        "EventChain",
        "EventHandler",
        "background",
        "call_script",
        "clear_local_storage",
        "console_log",
        "download",
        "prevent_default",
        "redirect",
        "remove_cookie",
        "remove_local_storage",
        "set_clipboard",
        "set_focus",
        "scroll_to",
        "set_value",
        "stop_propagation",
        "upload_files",
        "window_alert",
    ],
    "reflex.middleware": ["middleware", "Middleware"],
    "reflex.model": ["model", "session", "Model"],
    "reflex.page": ["page"],
    "reflex.route": ["route"],
    "reflex.state": [
        "state",
        "var",
        "Cookie",
        "LocalStorage",
        "ComponentState",
        "State",
    ],
    "reflex.style": ["style", "toggle_color_mode"],
    "reflex.testing": ["testing"],
    "reflex.utils": ["utils"],
    "reflex.utils.imports": ["ImportVar"],
    "reflex.vars": ["vars", "cached_var", "Var"],
}


def _reverse_mapping(mapping: dict[str, list]) -> dict[str, str]:
    """Reverse the mapping used to lazy loading, and check for conflicting name.

    Args:
        mapping: The mapping to reverse.

    Returns:
        The reversed mapping.
    """
    reversed_mapping = {}
    for key, values in mapping.items():
        for value in values:
            if value not in reversed_mapping:
                reversed_mapping[value] = key
            else:
                console.warn(
                    f"Key {value} is present multiple times in the imports _MAPPING: {key} / {reversed_mapping[value]}"
                )
    return reversed_mapping


# _MAPPING = {value: key for key, values in _MAPPING.items() for value in values}
_MAPPING = _reverse_mapping(_MAPPING)


def _removeprefix(text, prefix):
    return text[text.startswith(prefix) and len(prefix):]


__all__ = (_removeprefix(mod, "reflex.") for mod in _MAPPING)


def __getattr__(name: str) -> Type:
    """Lazy load all modules.

    Args:
        name: name of the module to load.

    Returns:
        The module or the attribute of the module.

    Raises:
        AttributeError: If the module or the attribute does not exist.
    """
    try:
        # Check for import of a module that is not in the mapping.
        if name not in _MAPPING:
            # If the name does not start with reflex, add it.
            if not name.startswith("reflex") and name != "__all__":
                name = f"reflex.{name}"
            return importlib.import_module(name)

        # Import the module.
        module = importlib.import_module(_MAPPING[name])

        # Get the attribute from the module if the name is not the module itself.
        return (
            getattr(module, name) if name != _MAPPING[name].rsplit(".")[-1] else module
        )
    except ModuleNotFoundError:
        raise AttributeError(f"module 'reflex' has no attribute {name}") from None
