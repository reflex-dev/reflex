import reflex as rx

config = rx.Config(
    app_name="quiz",
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                has_background=True,
                radius="none",
                accent_color="orange",
                appearance="light",
            ),
        ),
    ],
)
