import reflex as rx

config = rx.Config(
    app_name="blog",
    db_url="sqlite:///reflex.db",
    async_db_url="sqlite+aiosqlite:///reflex.db",
    plugins=[rx.plugins.SitemapPlugin()],
)
