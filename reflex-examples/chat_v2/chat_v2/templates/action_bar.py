import reflex as rx


def action_bar(
    has_token: bool = False,
):
    return rx.hstack(
        rx.hstack(
            *[
                rx.icon(
                    tag=name,
                    size=18,
                    color=rx.color("slate", 11),
                )
                for name in [
                    "rotate-cw",
                    "book-copy",
                    "share-2",
                    "bookmark",
                    "ellipsis-vertical",
                ]
            ],
            align="center",
            display="flex",
        ),
        rx.cond(
            has_token,
            rx.badge(
                "50 Token",
                padding="6px",
                radius="medium",
                box_shadow=rx.color_mode_cond(
                    light="0px 1px 3px rgba(25, 33, 61, 0.1)",
                    dark="0px 1px 3px rgba(25, 33, 61, 0.1)",
                ),
            ),
            rx.spacer(),
        ),
        display="flex",
        align="center",
        justify="between",
        width="100%",
        gap="10px",
    )
