import reflex as rx

config = rx.Config(
    app_name="counter",
    env=rx.Env.DEV,
    plugins=[rx.plugins.RadixThemesPlugin()],
)
