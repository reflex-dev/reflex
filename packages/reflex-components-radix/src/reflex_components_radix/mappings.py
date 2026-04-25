"""Radix component mappings for lazy loading."""

from reflex_base.utils.lazy_loader import SubmodAttrsType

RADIX_THEMES_MAPPING: SubmodAttrsType = {
    "reflex_components_radix.themes.base": ["color_mode", "theme", "theme_panel"],
    "reflex_components_radix.themes.color_mode": ["color_mode"],
}
RADIX_THEMES_COMPONENTS_MAPPING: SubmodAttrsType = {
    **{
        f"reflex_components_radix.themes.components.{mod}": [mod]
        for mod in [
            "alert_dialog",
            "aspect_ratio",
            "avatar",
            "badge",
            "button",
            "callout",
            "card",
            "checkbox",
            "context_menu",
            "data_list",
            "dialog",
            "hover_card",
            "icon_button",
            "input",
            "inset",
            "popover",
            "scroll_area",
            "select",
            "skeleton",
            "slider",
            "spinner",
            "switch",
            "table",
            "tabs",
            "text_area",
            "tooltip",
            "segmented_control",
            "radio_cards",
            "checkbox_cards",
            "checkbox_group",
        ]
    },
    "reflex_components_radix.themes.components.text_field": ["text_field", "input"],
    "reflex_components_radix.themes.components.radio_group": ["radio", "radio_group"],
    "reflex_components_radix.themes.components.dropdown_menu": [
        "menu",
        "dropdown_menu",
    ],
    "reflex_components_radix.themes.components.separator": ["divider", "separator"],
    "reflex_components_radix.themes.components.progress": ["progress"],
}

RADIX_THEMES_LAYOUT_MAPPING: SubmodAttrsType = {
    "reflex_components_radix.themes.layout.box": [
        "box",
    ],
    "reflex_components_radix.themes.layout.center": [
        "center",
    ],
    "reflex_components_radix.themes.layout.container": [
        "container",
    ],
    "reflex_components_radix.themes.layout.flex": [
        "flex",
    ],
    "reflex_components_radix.themes.layout.grid": [
        "grid",
    ],
    "reflex_components_radix.themes.layout.section": [
        "section",
    ],
    "reflex_components_radix.themes.layout.spacer": [
        "spacer",
    ],
    "reflex_components_radix.themes.layout.stack": [
        "stack",
        "hstack",
        "vstack",
    ],
    "reflex_components_radix.themes.layout.list": [
        ("list_ns", "list"),
        "list_item",
        "ordered_list",
        "unordered_list",
    ],
}

RADIX_THEMES_TYPOGRAPHY_MAPPING: SubmodAttrsType = {
    "reflex_components_radix.themes.typography.blockquote": [
        "blockquote",
    ],
    "reflex_components_radix.themes.typography.code": [
        "code",
    ],
    "reflex_components_radix.themes.typography.heading": [
        "heading",
    ],
    "reflex_components_radix.themes.typography.link": [
        "link",
    ],
    "reflex_components_radix.themes.typography.text": [
        "text",
    ],
}

RADIX_PRIMITIVES_MAPPING: SubmodAttrsType = {
    "reflex_components_radix.primitives.accordion": [
        "accordion",
    ],
    "reflex_components_radix.primitives.drawer": [
        "drawer",
    ],
    "reflex_components_radix.primitives.form": [
        "form",
    ],
    "reflex_components_radix.primitives.progress": [
        "progress",
    ],
}

RADIX_PRIMITIVES_SHORTCUT_MAPPING: SubmodAttrsType = {
    k: v for k, v in RADIX_PRIMITIVES_MAPPING.items() if "progress" not in k
}

RADIX_MAPPING: SubmodAttrsType = {
    **RADIX_THEMES_MAPPING,
    **RADIX_THEMES_COMPONENTS_MAPPING,
    **RADIX_THEMES_TYPOGRAPHY_MAPPING,
    **RADIX_THEMES_LAYOUT_MAPPING,
    **RADIX_PRIMITIVES_SHORTCUT_MAPPING,
}
