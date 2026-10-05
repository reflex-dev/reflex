"""Configure self-hosted production and optional Redis runtime exploration."""

import os

import reflex as rx

config = rx.Config(
    app_name="lifecycle_app",
    frontend_path=os.environ.get("QA_FRONTEND_PATH", ""),
    redis_url=os.environ.get("QA_REDIS_URL"),
    state_manager_mode="redis" if os.environ.get("QA_REDIS_URL") else "disk",
    plugins=[rx.plugins.RadixThemesPlugin()],
)
