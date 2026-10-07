import reflex as rx

config = rx.Config(
    app_name="local_auth_demo",
    db_url="sqlite:///reflex.db",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(has_background=True, accent_color="orange"),
        ),
    ],
)
