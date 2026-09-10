import os

import reflex as rx

config = rx.Config(
    app_name="routes_app",
    telemetry_enabled=False,
    frontend_path=os.environ.get("HP_FRONTEND_PATH", ""),
)
