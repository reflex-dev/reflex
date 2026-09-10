import reflex as rx

config = rx.Config(
    app_name="bgflush_app",
    telemetry_enabled=False,
    plugins=[rx.plugins.SitemapPlugin(), rx.plugins.RadixThemesPlugin()],
)
