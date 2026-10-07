"""Configuration for separately deployed static frontend and backend."""

import reflex as rx

config = rx.Config(
    app_name="deploy_app",
    api_url="http://localhost:8730",
    deploy_url="http://localhost:3730",
    state_manager_mode="memory",
    telemetry_enabled=False,
    plugins=[],
)
