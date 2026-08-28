import reflex as rx

config = rx.Config(
    app_name="form_designer",
    db_url="sqlite:///reflex.db",
    plugins=[
        rx.plugins.sitemap.SitemapPlugin(),
        rx.plugins.RadixThemesPlugin(theme=rx.theme(accent_color="blue")),
    ],
)
