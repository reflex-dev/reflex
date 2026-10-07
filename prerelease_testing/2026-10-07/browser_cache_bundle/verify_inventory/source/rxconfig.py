"""Independent inventory verifier configuration."""

import reflex as rx

config = rx.Config(
    app_name="inventory_app",
    telemetry_enabled=False,
    plugins=[rx.plugins.SitemapPlugin()],
)
