import reflex as rx

config = rx.Config(
    app_name="local_auth_min",
    db_url="sqlite:///reflex_min.db",
    plugins=[rx.plugins.SitemapPlugin(), rx.plugins.RadixThemesPlugin()],
)
