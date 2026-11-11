import reflex as rx

config = rx.Config(app_name="smoke", telemetry_enabled=False, plugins=[rx.plugins.RadixThemesPlugin(), rx.plugins.SitemapPlugin()])
