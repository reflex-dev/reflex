"""Point the isolated browser test exclusively at disposable Redis database 5."""

import reflex as rx

config = rx.Config(
    app_name="redis_probe",
    frontend_port=3111,
    backend_port=8111,
    api_url="http://localhost:8111",
    redis_url="redis://localhost:9141/5",
    state_manager_mode=rx.constants.StateManagerMode.REDIS,
    db_url="sqlite:///plain.sqlite",
    telemetry_enabled=False,
    plugins=[rx.plugins.RadixThemesPlugin()],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
