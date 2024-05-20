"""Radix themes components."""

FIELDS = [
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
    # progress is in experimental namespace until https://github.com/radix-ui/themes/pull/492
    # "progress",
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
]

import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submod_attrs={k: [k] if not k == "text_field" else [k, "input"] for k in FIELDS},
)