import reflex as rx


def chat_date_divider(
    divider_title_text: str,
):
    return rx.hstack(
        rx.divider(),
        rx.text(
            divider_title_text,
            color=rx.color(
                color="slate",
                shade=11,
            ),
            width="300px",
            align="center",
        ),
        rx.divider(),
        width="100%",
        align="center",
        justify="center",
    )
