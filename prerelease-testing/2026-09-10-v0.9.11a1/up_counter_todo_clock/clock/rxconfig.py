import reflex as rx

config = rx.Config(
    app_name="clock",
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                appearance="light",
                has_background=True,
                radius="large",
                accent_color="amber",
                gray_color="sand",
            ),
        ),
    ],
)
