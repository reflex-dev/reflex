"""Namespace for components provided by @radix-ui packages."""
import lazy_loader as lazy
from reflex import RADIX_MAPPING

v = {"".join(k.split("components.radix.")[-1]): v for k,v in RADIX_MAPPING.items()}
__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={"themes", "primitives"},
    submod_attrs= v
    # submod_attrs={
    #     "primitives.accordion": [
    #         "accordion",
    #     ],
    #     "primitives.drawer": [
    #         "drawer",
    #     ],
    #     "primitives.form": [
    #         "form",
    #     ],
    #     "primitives.slider": [
    #         "slider"
    #     ],
    #     "primitives.progress": [
    #         "progress",
    #     ],
    #     **{
    #         f"themes.components.{mod}": [mod] for mod in [
    #             "alert_dialog",
    #             "aspect_ratio",
    #             "avatar",
    #             "badge",
    #             "button",
    #             "callout",
    #             "card",
    #             "checkbox",
    #             # "checkbox_cards",
    #             # "checkbox_group",
    #             "context_menu",
    #             "data_list",
    #             "dialog",
    #             # "divider",
    #             "dropdown_menu",
    #             "hover_card",
    #             "icon_button",
    #             "input",
    #             "inset",
    #             "menu",
    #             "popover",
    #             "radio",
    #             # "radio_cards",
    #             "radio_group",
    #             "scroll_area",
    #             # "segmented_control",
    #             "select",
    #             # "separator",
    #             "skeleton",
    #             "slider",
    #             "spinner",
    #             "switch",
    #             "table",
    #             "tabs",
    #             "text_area",
    #             "tooltip",
    #         ]
    #     },
    #     "themes.components.text_field": [
    #         "text_field",
    #         "input"
    #     ],
    #     # "themes.components.radio": [
    #     #     "radio",
    #     #     "radio_group"
    #     # ],
    #     "themes.components.separator": [
    #         "divider",
    #     ],
    #     "themes.typography.blockquote": [
    #         "blockquote",
    #     ],
    #     "themes.typography.code": [
    #         "code",
    #     ],
    #     "themes.typography.heading": [
    #         "heading",
    #     ],
    #     "themes.typography.link": [
    #         "link",
    #     ],
    #     "themes.typography.text": [
    #         "text",
    #     ],
    #     "themes.layout.box": [
    #         "box",
    #     ],
    #     "themes.layout.center": [
    #         "center",
    #     ],
    #     "themes.layout.container": [
    #         "container",
    #     ],
    #     "themes.layout.flex": [
    #         "flex",
    #     ],
    #     "themes.layout.grid": [
    #         "grid",
    #     ],
    #     "themes.layout.section": [
    #         "section",
    #     ],
    #     "themes.layout.spacer": [
    #         "spacer",
    #     ],
    #     "themes.layout.stack": [
    #         "stack",
    #         "hstack",
    #         "vstack",
    #     ],
    #     "themes.layout.list": [
    #         "list",
    #         "list_item",
    #         "ordered_list",
    #         "unordered_list",
    #     ],
    # }
)