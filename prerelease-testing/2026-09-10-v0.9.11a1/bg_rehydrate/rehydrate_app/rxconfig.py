import reflex as rx

config = rx.Config(
    app_name="rehydrate_app",
    telemetry_enabled=False,
    plugins=[rx.plugins.SitemapPlugin(), rx.plugins.RadixThemesPlugin()],
)
