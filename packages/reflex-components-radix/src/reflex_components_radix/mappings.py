"""Radix component mappings for lazy loading."""

RADIX_THEMES_MAPPING: dict = {
    "components.radix.themes.base": ["color_mode", "theme", "theme_panel"],
    "components.radix.themes.color_mode": ["color_mode"],
}
RADIX_THEMES_COMPONENTS_MAPPING: dict = {
    **{
        f"components.radix.themes.components.{mod}": [mod]
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
    "components.radix.themes.components.text_field": ["text_field", "input"],
    "components.radix.themes.components.radio_group": ["radio", "radio_group"],
    "components.radix.themes.components.dropdown_menu": ["menu", "dropdown_menu"],
    "components.radix.themes.components.separator": ["divider", "separator"],
    "components.radix.themes.components.progress": ["progress"],
}

RADIX_THEMES_LAYOUT_MAPPING: dict = {
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
        ("list_ns", "list"),
        "list_item",
        "ordered_list",
        "unordered_list",
    ],
}

RADIX_THEMES_TYPOGRAPHY_MAPPING: dict = {
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

RADIX_PRIMITIVES_MAPPING: dict = {
    "components.radix.primitives.accordion": [
        "accordion",
    ],
    "components.radix.primitives.drawer": [
        "drawer",
    ],
    "components.radix.primitives.form": [
        "form",
    ],
    "components.radix.primitives.progress": [
        "progress",
    ],
}

RADIX_PRIMITIVES_SHORTCUT_MAPPING: dict = {
    k: v for k, v in RADIX_PRIMITIVES_MAPPING.items() if "progress" not in k
}

RADIX_MAPPING: dict = {
    **RADIX_THEMES_MAPPING,
    **RADIX_THEMES_COMPONENTS_MAPPING,
    **RADIX_THEMES_TYPOGRAPHY_MAPPING,
    **RADIX_THEMES_LAYOUT_MAPPING,
    **RADIX_PRIMITIVES_SHORTCUT_MAPPING,
}
