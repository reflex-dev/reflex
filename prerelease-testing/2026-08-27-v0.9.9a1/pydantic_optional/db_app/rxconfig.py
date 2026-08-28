import reflex as rx

config = rx.Config(
    app_name="db_app",
    db_url="sqlite:///reflex.db",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)
