"""Import all classes and functions the end user will need to make an app.

Anything imported here will be available in the default Reflex import as `rx.*`.
To signal to typecheckers that something should be reexported,
we use the Flask "import name as name" syntax.
"""

from __future__ import annotations


RADIX_MAPPING = {
    "components.radix.themes": [
        "color_mode",
        "theme",
        "theme_panel"
    ],
    "components.radix.themes.layout.box": [
        "box",
    ],
    "components.radix.themes.layout.center": [
        "center",
    ],
    "components.radix.themes.layout.container": [
        "container",
    ],
    "components.radix.themes.layout.flex": [
        "flex",
    ],
    "components.radix.themes.layout.grid": [
        "grid",
    ],
    "components.radix.themes.layout.section": [
        "section",
    ],
    "components.radix.themes.layout.spacer": [
        "spacer",
    ],
    "components.radix.themes.layout.stack": [
        "stack",
        "hstack",
        "vstack",
    ],
    "components.radix.themes.layout.list": [
        "list",
        "list_item",
        "ordered_list",
        "unordered_list",
    ],
    "components.radix.primitives.accordion": [
        "accordion",
    ],
    "components.radix.primitives.drawer": [
        "drawer",
    ],
    "components.radix.primitives.form": [
        "form",
    ],
    # "components.radix.primitives.slider": [
    #     "slider"
    # ],
    "components.radix.primitives.progress": [
        "progress",
    ],
    **{
        f"components.radix.themes.components.{mod}": [mod] for mod in [
            "alert_dialog",
            "aspect_ratio",
            "avatar",
            "badge",
            "button",
            "callout",
            "card",
            "checkbox",
            # "checkbox_cards",
            # "checkbox_group",
            "context_menu",
            "data_list",
            "dialog",
            # "divider",
            # "dropdown_menu",
            "hover_card",
            "icon_button",
            "input",
            "inset",
            # "menu",
            "popover",
            # "radio",
            # "radio_cards",
            # "radio_group",
            "scroll_area",
            # "segmented_control",
            "select",
            # "separator",
            "skeleton",
            "slider",
            "spinner",
            "switch",
            "table",
            "tabs",
            "text_area",
            "tooltip",
        ]
    },

    "components.radix.themes.components.text_field": [
        "text_field",
        "input"
    ],
    "components.radix.themes.components.radio_group": [
        "radio",
        "radio_group"
    ],
    "components.radix.themes.components.dropdown_menu": [
        "menu",
        "dropdown_menu"
    ],
    "components.radix.themes.components.separator": [
        "divider",
        "separator"
    ],
    "components.radix.themes.typography.blockquote": [
        "blockquote",
    ],
    "components.radix.themes.typography.code": [
        "code",
    ],
    "components.radix.themes.typography.heading": [
        "heading",
    ],
    "components.radix.themes.typography.link": [
        "link",
    ],
    "components.radix.themes.typography.text": [
        "text",
    ],
}

_MAPPING = {
    "experimental": ["_x"],
    "admin": ["AdminDash"],
    "app": ["App", "UploadFile"],
    "base": ["Base"],
    "components.component": ["Component", "NoSSRComponent", "memo"],

    # "components.chakra": ["chakra"],
    # "components": ["el"],
    "components.el.elements.media": ["image"],
    "components.lucide": ["icon"],
    "components.base.fragment": [
        "fragment",
        "Fragment",
    ],
    "components.base.script": [
        "script",
        "Script"
    ],
    "components.suneditor": [
        "editor",
        "EditorButtonList",
        "EditorOptions",
    ],
    "components": ["el", "chakra", "radix", "lucide", "recharts"],
    "components.markdown": ["markdown"],
    "components.next": ["next"],
    # "components.radix": ["radix", "color_mode"],

    **RADIX_MAPPING,
    "components.plotly": ["plotly"],
    "components.react_player": [
        "audio",
        "video"
    ],

    "components.core.banner": [
        "connection_banner",
        "connection_modal",
    ],
    "components.core.cond": [
        "cond",
        "color_mode_cond"
    ],
    "components.core.foreach": [
        "foreach"
    ],
    "components.core.debounce": [
        "debounce_input"
    ],
    "components.core.html": [
        "html"
    ],
    "components.core.match": [
        "match"
    ],
    "components.core.colors": [
        "color"
    ],
    "components.core.responsive": [
        "desktop_only",
        "mobile_and_tablet",
        "mobile_only",
        "tablet_and_desktop",
        "tablet_only",
    ],
    "components.core.upload": [
        "cancel_upload",
        "clear_selected_files",
        "get_upload_dir",
        "get_upload_url",
        "selected_files",
        "upload",
    ],
    "components.datadisplay.code": [
        "code_block",
    ],
    "components.datadisplay.dataeditor": [
        "data_editor",
        "data_editor_theme",
    ],
    "components.datadisplay.logo": [
        "logo"
    ],
    "components.gridjs": ["data_table"],
    # "components.recharts": ["recharts"],
    "components.moment": ["MomentDelta", "moment"],
    "config": ["Config", "DBConfig"],
    "constants": ["constants", "Env"],
    "event": [
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
    "middleware": ["middleware", "Middleware"],
    "model": ["session", "Model"],
    "page": ["page"],
    "state": [
        "state",
        "var",
        "Cookie",
        "LocalStorage",
        "ComponentState",
        "State",
    ],
    "style": ["Style", "toggle_color_mode"],
    "utils.imports": ["ImportVar"],
    "vars": ["cached_var", "Var"],
}

import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={"components", "event", "app", "style", "page", "admin", "base", "model", "testing", "utils", "vars", "config", "compiler"},
    submod_attrs=_MAPPING,
)
