"""Configure the isolated published-alpha upload-stream app."""

import reflex as rx

config = rx.Config(
    app_name="upload_probe",
    frontend_port=3111,
    backend_port=8111,
    api_url="http://localhost:8111",
    telemetry_enabled=False,
    plugins=[rx.plugins.RadixThemesPlugin()],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
