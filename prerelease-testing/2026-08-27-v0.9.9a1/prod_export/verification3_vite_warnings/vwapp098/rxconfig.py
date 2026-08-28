import reflex as rx

config = rx.Config(
    app_name="vwapp098",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)