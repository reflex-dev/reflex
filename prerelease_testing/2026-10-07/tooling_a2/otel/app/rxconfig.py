"""Configure the documented browser tracing plugin for a local collector."""

import reflex as rx
from reflex_otel import OtelPlugin

config = rx.Config(
    app_name="telemetry_app",
    telemetry_enabled=False,
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.RadixThemesPlugin(),
        OtelPlugin(
            endpoint="http://localhost:8588/v1/traces",
            service_name="qa-frontend",
            headers={"x-qa-collector": "public-fixture"},
            render_timing=True,
        ),
    ],
)
