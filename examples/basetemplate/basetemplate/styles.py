import reflex as rx


border_radius = ("0.375rem",)
box_shadow = ("0px 0px 0px 1px rgba(84, 82, 95, 0.14)",)
border = "1px solid #F4F3F6"
text_color = "black"
accent_text_color = "#1A1060"
accent_color = "#F5EFFE"

base_style = {
    rx.MenuItem: {
        "_hover": {
            "bg": accent_color,
        },
    },
}
