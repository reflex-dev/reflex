import reflex as rx

config = rx.Config(
    app_name="sea",
    plugins=[rx.plugins.SitemapPlugin(), rx.plugins.RadixThemesPlugin()],
)
