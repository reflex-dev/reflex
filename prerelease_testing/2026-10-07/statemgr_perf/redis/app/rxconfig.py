"""Configure the real Redis pool and persistence test app."""

import reflex as rx

config = rx.Config(app_name="redis_app", telemetry_enabled=False)
