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
    "hover_card",
    "icon_button",
    "input",
    "inset",
    "popover",
    # progress is in experimental namespace until https://github.com/radix-ui/themes/pull/492
    # "progress",
    "radio_cards",
    "scroll_area",
    "segmented_control",
    "select",
    "skeleton",
    "slider",
    "spinner",
    "switch",
    "table",
    "tabs",
    "text_area",
    "tooltip",
]
EXTRAS = {
    "text_field": [
        "text_field",
        "input"
    ],
    "separator": [
        "separator",
        "divider"
    ],
    "dropdown_menu": [
        "dropdown_menu",
        "menu"
    ],
    "radio_group":[
        "radio",
        "radio_group"
    ],

}
import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submod_attrs={**{k: [k] for k in FIELDS}, **EXTRAS},
)
