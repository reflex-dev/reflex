import reflex as rx

config = rx.Config(
    app_name="snakegame",
    env=rx.Env.DEV,
    plugins=[rx.plugins.RadixThemesPlugin()],
)
