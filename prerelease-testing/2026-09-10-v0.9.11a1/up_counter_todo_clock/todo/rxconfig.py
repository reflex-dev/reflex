import reflex as rx

config = rx.Config(
    app_name="todo",
    env=rx.Env.DEV,
    plugins=[rx.plugins.RadixThemesPlugin()],
)
