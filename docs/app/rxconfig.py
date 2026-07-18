import reflex as rx
from reflex_site_shared.plugins import SharedSiteStylesPlugin

from agent_files import AgentFilesPlugin

config = rx.Config(
    app_name="reflex_docs",
    frontend_path="/docs",
    frontend_packages=[
        "tailwindcss-animated@2.0.0",
        "tailwindcss-scroll-mask@0.0.3",
        "es-toolkit@1.46.1",
        "@fontsource-variable/instrument-sans@5.2.8",
        "@fontsource-variable/jetbrains-mono@5.2.8",
    ],
    telemetry_enabled=False,
    plugins=[
        rx.plugins.TailwindV4Plugin(),
        SharedSiteStylesPlugin(),
        rx.plugins.SitemapPlugin(trailing_slash="always"),
        AgentFilesPlugin(),
    ],
)
