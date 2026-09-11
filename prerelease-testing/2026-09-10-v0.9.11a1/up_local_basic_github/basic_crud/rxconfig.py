import reflex as rx

config = rx.Config(
    app_name="basic_crud",
    db_url="sqlite:///reflex.db",
    plugins=[rx.plugins.RadixThemesPlugin()],
)
