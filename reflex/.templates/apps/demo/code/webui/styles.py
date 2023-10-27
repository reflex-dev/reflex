import reflex as rx

bg_dark_color = "#111"
bg_medium_color = "#222"

border_color = "#fff3"

accennt_light = "#6649D8"
accent_color = "#5535d4"
accent_dark = "#4c2db3"

icon_color = "#fff8"

text_light_color = "#fff"
shadow_light = "rgba(17, 12, 46, 0.15) 0px 48px 100px 0px;"
shadow = "rgba(50, 50, 93, 0.25) 0px 50px 100px -20px, rgba(0, 0, 0, 0.3) 0px 30px 60px -30px, rgba(10, 37, 64, 0.35) 0px -2px 6px 0px inset;"

message_style = dict(display="inline-block", p="4", border_radius="xl", max_w="30em")

input_style = dict(
    bg=bg_medium_color,
    border_color=border_color,
    border_width="1px",
    p="4",
)

icon_style = dict(
    font_size="md",
    color=icon_color,
    _hover=dict(color=text_light_color),
    cursor="pointer",
    w="8",
)

sidebar_style = dict(
    border="double 1px transparent;",
    border_radius="10px;",
    background_image=f"linear-gradient({bg_dark_color}, {bg_dark_color}), radial-gradient(circle at top left, {accent_color},{accent_dark});",
    background_origin="border-box;",
    background_clip="padding-box, border-box;",
    p="2",
    _hover=dict(
        background_image=f"linear-gradient({bg_dark_color}, {bg_dark_color}), radial-gradient(circle at top left, {accent_color},{accennt_light});",
    ),
)

base_style = {
    rx.Avatar: {
        "shadow": shadow,
        "color": text_light_color,
        # "bg": border_color,
    },
    rx.Button: {
        "shadow": shadow,
        "color": text_light_color,
        "_hover": {
            "bg": accent_dark,
        },
    },
    rx.Menu: {
        "bg": bg_dark_color,
        "border": f"red",
    },
    rx.MenuList: {
        "bg": bg_dark_color,
        "border": f"1.5px solid {bg_medium_color}",
    },
    rx.MenuDivider: {
        "border": f"1px solid {bg_medium_color}",
    },
    rx.MenuItem: {
        "bg": bg_dark_color,
        "color": text_light_color,
    },
    rx.DrawerContent: {
        "bg": bg_dark_color,
        "color": text_light_color,
        "opacity": "0.9",
    },
    rx.Hstack: {
        "align_items": "center",
        "justify_content": "space-between",
    },
    rx.Vstack: {
        "align_items": "stretch",
        "justify_content": "space-between",
    },
}
