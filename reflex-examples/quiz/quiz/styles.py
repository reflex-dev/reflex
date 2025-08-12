import reflex as rx

base_style = {
    "padding": "2em",
    "border_radius": "25px",
    "border": f"1px solid {rx.color('accent', 12)}",
    "box_shadow": f"0px 0px 10px 0px {rx.color('gray', 11)}",
    "bg": rx.color("gray", 1),
}

question_style = base_style | {"width": "100%"}

page_background = rx.color("gray", 3)
