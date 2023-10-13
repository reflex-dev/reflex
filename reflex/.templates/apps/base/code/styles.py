"""Styles for the app."""
import reflex as rx

border_radius = ("0.375rem",)
box_shadow = ("0px 0px 0px 1px rgba(84, 82, 95, 0.14)",)
border = "1px solid #F4F3F6"
text_color = "black"
accent_text_color = "#1A1060"
accent_color = "#F5EFFE"

template_page_style = {
    "height": "100vh",
    "width": "100%",
    "padding_top": "5em",
    "padding_x": "2em",
}

template_content_style = {
    "width": "100%",
    "align_items": "flex-start",
    "height": "90%",
    "box_shadow": "0px 0px 0px 1px rgba(84, 82, 95, 0.14)",
    "border_radius": border_radius,
    "padding": "1em",
}

link_style = {
    "color": text_color,
    "text_decoration": "none",
    "_hover": {
        "color": accent_color,
    },
}

base_style = {
    rx.MenuItem: {
        "_hover": {
            "bg": accent_color,
        },
    },
}
