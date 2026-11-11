import reflex as rx

config = rx.Config(
    app_name="chat_v2",
    db_url="sqlite:///reflex.db",
    plugins=[rx.plugins.RadixThemesPlugin()],
)
