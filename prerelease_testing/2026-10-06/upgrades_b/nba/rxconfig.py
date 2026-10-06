import reflex as rx

config = rx.Config(
    app_name="nba",
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                appearance="light",
                has_background=True,
                radius="large",
                accent_color="orange",
            ),
        ),
    ],
)
