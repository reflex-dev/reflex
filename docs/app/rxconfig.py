import os

import reflex as rx

from agent_files import AgentFilesPlugin

config = rx.Config(
    app_name="reflex_docs",
    deploy_url="https://reflex.dev",
    frontend_path=os.environ.get("REFLEX_FRONTEND_PATH", "/docs"),
    frontend_packages=[
        "tailwindcss-animated",
    ],
    telemetry_enabled=False,
    plugins=[
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.SitemapPlugin(trailing_slash="always"),
        AgentFilesPlugin(),
    ],
)
