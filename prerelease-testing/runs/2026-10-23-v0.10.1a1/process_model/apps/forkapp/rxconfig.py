import reflex as rx

config = rx.Config(
    app_name="forkapp",
    db_url="sqlite:///forkapp.db",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(),
    ],
)
