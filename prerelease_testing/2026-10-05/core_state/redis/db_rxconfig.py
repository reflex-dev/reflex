"""Configure isolated SQLite migrations with published alpha wheels."""

import reflex as rx

config = rx.Config(
    app_name="plain_db",
    frontend_port=3112,
    backend_port=8112,
    db_url="sqlite:///plain.sqlite",
    telemetry_enabled=False,
    plugins=[rx.plugins.RadixThemesPlugin()],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
