from typing import Callable

import reflex as rx

from chat_v2.components.badges import badge_with_icon
from chat_v2.components.buttons import button_with_icon
from chat_v2.components.typography import text_with_icon

from .search_box import search_bar_with_sidebar_shortcut
from .select import select_menu

__prompts__ = [
    [
        "Vivamus suscipit tortor eget",
        "Phasellus volutpat metus ac urna egestas, sed consequat quam lacinia.",
    ],
    [
        "Integer malesuada nunc vel",
        "Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae.",
    ],
    [
        "Nullam quis risus eget urna",
        "Donec ullamcorper nulla non metus auctor fringilla. Vestibulum dapibus nunc ac augue.",
    ],
    [
        "Etiam sit amet orci eget",
        "Cras ultricies ligula sed magna dictum porta. Integer tincidunt nulla in velit.",
    ],
    [
        "Curabitur non nulla sit amet",
        "Quisque velit nisi, pretium ut lacinia in, elementum id enim. Proin eget tortor risus.",
    ],
    [
        "Sed porttitor lectus nibh",
        "Mauris blandit aliquet elit, eget tincidunt nibh pulvinar a. Curabitur arcu erat, accumsan id imperdiet et.",
    ],
    [
        "Aliquam erat volutpat",
        "Cras ultricies ligula sed magna dictum porta. Nulla quis lorem ut libero malesuada feugiat.",
    ],
    [
        "Quisque velit nisi",
        "Vestibulum ac diam sit amet quam vehicula elementum sed sit amet dui.",
    ],
    [
        "Mauris blandit aliquet",
        "Nulla porttitor accumsan tincidunt. Nulla quis lorem ut libero malesuada feugiat.",
    ],
    [
        "Pellentesque in ipsum",
        "Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae.",
    ],
]


class PromptLibrary(rx.State):
    def create_new_prompt_entry(
        self,
    ) -> None:
        pass


border = rx.color_mode_cond(
    f"1px solid {rx.color('indigo', 3)}",
    f"1px solid {rx.color('slate', 7, True)}",
)
background = rx.color_mode_cond(
    rx.color("indigo", 1),
    rx.color("indigo", 3),
)

box_shadow = rx.color_mode_cond("0px 1px 3px rgba(25, 33, 61, 0.1)", "none")


title = rx.hstack(
    rx.text("Prompt Library"),
    rx.dialog.close(
        rx.icon(tag="x", size=20),
    ),
    width="100%",
    align="center",
    justify="between",
)


menu = rx.vstack(
    rx.hstack(
        search_bar_with_sidebar_shortcut(width="100%"),
        select_menu("list-filter", "Sort by"),
        width="100%",
    ),
    rx.hstack(
        rx.hstack(
            text_with_icon(
                "book",
                "My prompts",
                padding="10px",
                background=background,
                box_shadow=box_shadow,
                border_radius="8px",
            ),
            text_with_icon(
                "users",
                "Community",
                padding="10px",
                border=border,
                border_radius="8px",
            ),
            width="100%",
            justify="start",
        ),
        rx.hstack(
            button_with_icon(
                "Create",
                "plus",
                on_click=PromptLibrary.create_new_prompt_entry,
            ),
            rx.box(
                rx.icon(tag="folder", size=15, color=rx.color("slate", 11)),
                border=border,
                padding="10px",
                border_radius="8px",
            ),
            width="100%",
            align="center",
            justify="end",
        ),
        width="100%",
        align="center",
        justify="between",
    ),
    width="100%",
    spacing="4",
    padding="5px 0px 16px 0px",
)


def prompt_item(
    title: str,
    description: str,
):
    return rx.hstack(
        rx.vstack(
            rx.text(title, weight="bold", color=rx.color("slate", 12)),
            rx.text(
                description,
                width="100%",
                overflow="hidden",
                font_family="Inter",
                white_space="nowrap",
                text_overflow="ellipsis",
                color=rx.color("slate", 11),
            ),
            flex="3",
            justify="center",
            align="start",
            spacing="1",
            overflow_x="hidden",
        ),
        rx.hstack(
            *[badge_with_icon(name) for name in ["move-up-right", "ellipsis-vertical"]],
            flex="1",
            align="center",
            justify="end",
        ),
        width="100%",
        align="center",
        justify="between",
        gap="16px",
        border_bottom=rx.color_mode_cond(
            f"2px solid {rx.color('indigo', 3)}",
            f"1px solid {rx.color('slate', 7, True)}",
        ),
        padding_bottom="16px",
    )


prompts = rx.vstack(
    *[prompt_item(title, description) for title, description in __prompts__],
    width="100%",
    height="30em",
    overflow="scroll",
    spacing="5",
    padding="16px 0px",
)


class LibraryPrompt(rx.State):
    is_open: bool = False

    def toggle_prompt_library(
        self,
    ) -> None:
        self.is_open = not self.is_open


def dialog_library_base(
    *args,
    on_create_new_chat: Callable,
):
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(title),
            rx.dialog.description(
                menu,
                rx.divider(),
                *args,
                width="100%",
                gap="12px",
            ),
            rx.box(
                position="absolute",
                bottom="0",
                left="0",
                width="100%",
                height="20%",
                background=f"linear-gradient(360deg,{rx.color('indigo', 2)}, transparent);",
                gap="40px",
            ),
            background_color=rx.color_mode_cond(
                "",
                rx.color(
                    "indigo",
                    2,
                ),
            ),
            height="40em",
            overflow="hidden",
            on_interact_outside=LibraryPrompt.toggle_prompt_library(),
        ),
        open=LibraryPrompt.is_open,
    )


def dialog_library():
    return dialog_library_base(
        prompts,
        on_create_new_chat=PromptLibrary.create_new_prompt_entry,
    )
