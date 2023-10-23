"""Styles for the app."""
import reflex as rx

border_radius = "0.375rem"
box_shadow = "0px 0px 0px 1px rgba(84, 82, 95, 0.14)"
border = "1px solid #F4F3F6"
text_color = "black"
accent_text_color = "#1A1060"
accent_color = "#F5EFFE"
hover_accent_color = {"_hover": {"color": accent_color}}
hover_accent_bg = {"_hover": {"bg": accent_color}}

template_page_style = {
    "width": "100%",
    "padding_top": "5em",
    "padding_x": "2em",
}

template_content_style = {
    "align_items": "flex-start",
    "box_shadow": box_shadow,
    "border_radius": border_radius,
    "padding": "1em",
    "margin_bottom": "2em",
}

link_style = {
    "color": text_color,
    "text_decoration": "none",
    **hover_accent_color,
}

base_style = {
    rx.MenuButton: {
        "width": "3em",
        "height": "3em",
        "background_color": "white",
        "border": border,
        "border_radius": border_radius,
        **hover_accent_bg,
    },
    rx.MenuItem: hover_accent_bg,
}
