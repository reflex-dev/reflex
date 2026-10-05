"""Configure the independent many-state production test."""

import reflex as rx

config = rx.Config(
    app_name="lifecycle_app",
    frontend_port=3133,
    backend_port=8133,
    telemetry_enabled=False,
    state_manager_mode="disk",
    plugins=[rx.plugins.RadixThemesPlugin()],
)
