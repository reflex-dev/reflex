import reflex as rx

config = rx.Config(
    app_name="pyd_app_098",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)