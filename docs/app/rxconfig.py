import reflex as rx
from reflex_site_shared.plugins import SharedSiteStylesPlugin

from agent_files import AgentFilesPlugin

config = rx.Config(
    app_name="reflex_docs",
    frontend_path="/docs",
    frontend_packages=[
        "tailwindcss-animated@2.1.0",
        "tailwindcss-scroll-mask@0.0.5",
        "@fontsource-variable/instrument-sans@5.3.0",
        "@fontsource-variable/jetbrains-mono@5.3.0",
    ],
    telemetry_enabled=False,
    plugins=[
        rx.plugins.TailwindV4Plugin(),
        SharedSiteStylesPlugin(),
        rx.plugins.SitemapPlugin(trailing_slash="always"),
        AgentFilesPlugin(),
    ],
)
