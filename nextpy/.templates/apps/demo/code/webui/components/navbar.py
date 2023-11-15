import nextpy as xt

from ...webui import styles
from ...webui.state import State


def navbar():
    return xt.box(
        xt.hstack(
            xt.hstack(
                xt.icon(
                    tag="hamburger",
                    mr=4,
                    on_click=State.toggle_drawer,
                    cursor="pointer",
                ),
                xt.link(
                    xt.box(
                        xt.image(src="favicon.ico", width=30, height="auto"),
                        p="1",
                        border_radius="6",
                        bg="#F0F0F0",
                        mr="2",
                    ),
                    href="/",
                ),
                xt.breadcrumb(
                    xt.breadcrumb_item(
                        xt.heading("NextpyGPT", size="sm"),
                    ),
                    xt.breadcrumb_item(
                        xt.text(State.current_chat, size="sm", font_weight="normal"),
                    ),
                ),
            ),
            xt.hstack(
                xt.button(
                    "+ New chat",
                    bg=styles.accent_color,
                    px="4",
                    py="2",
                    h="auto",
                    on_click=State.toggle_modal,
                ),
                xt.menu(
                    xt.menu_button(
                        xt.avatar(name="User", size="md"),
                        xt.box(),
                    ),
                    xt.menu_list(
                        xt.menu_item("Help"),
                        xt.menu_divider(),
                        xt.menu_item("Settings"),
                    ),
                ),
                spacing="8",
            ),
            justify="space-between",
        ),
        bg=styles.bg_dark_color,
        backdrop_filter="auto",
        backdrop_blur="lg",
        p="4",
        border_bottom=f"1px solid {styles.border_color}",
        position="sticky",
        top="0",
        z_index="100",
    )
