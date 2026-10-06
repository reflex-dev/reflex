import reflex as rx

config = rx.Config(
    app_name="dbmig",
    db_url="sqlite:///reflex.db",
    plugins=[rx.plugins.SitemapPlugin()],
    telemetry_enabled=False,
)
