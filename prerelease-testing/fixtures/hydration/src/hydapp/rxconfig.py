import os

import reflex as rx

config = rx.Config(
    app_name="hydapp",
    telemetry_enabled=False,
    plugins=[rx.plugins.RadixThemesPlugin()],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
