import reflex as rx

config = rx.Config(
    app_name="slashauth",
    db_url="sqlite:///reflex.db",
    plugins=[rx.plugins.RadixThemesPlugin()],
)
