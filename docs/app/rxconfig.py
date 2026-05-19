import reflex as rx

from agent_files import AgentFilesPlugin

config = rx.Config(
    app_name="reflex_docs",
    frontend_path="/docs",
    frontend_packages=[
        "tailwindcss-animated@2.0.0",
        "tailwindcss-scroll-mask@0.0.3@2.0.0",
    ],
    telemetry_enabled=False,
    plugins=[
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.SitemapPlugin(trailing_slash="always"),
        AgentFilesPlugin(),
    ],
)
