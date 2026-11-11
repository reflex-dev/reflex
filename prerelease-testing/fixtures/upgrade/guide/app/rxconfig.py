import reflex as rx

config = rx.Config(
    app_name="guideapp",
    plugins=[rx.plugins.SitemapPlugin(), rx.plugins.RadixThemesPlugin()],
)
