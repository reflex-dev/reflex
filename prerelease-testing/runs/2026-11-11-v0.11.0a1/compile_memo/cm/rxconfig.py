import reflex as rx

config = rx.Config(
    app_name="cm",
    telemetry_enabled=False,
    plugins=[rx.plugins.RadixThemesPlugin()],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
