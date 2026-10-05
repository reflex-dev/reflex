"""Configuration for the isolated published-wheel component dashboard."""

import os

import reflex as rx

config = rx.Config(
    app_name="component_dashboard",
    frontend_port=3121,
    backend_port=8121,
    api_url=os.environ.get("COMPONENT_API_URL", "http://localhost:8121"),
    telemetry_enabled=False,
    plugins=[rx.plugins.RadixThemesPlugin()],
)
