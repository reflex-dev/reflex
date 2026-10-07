import reflex as rx

config = rx.Config(app_name="dbapp", db_url="sqlite:///reflex.db", plugins=[rx.plugins.SitemapPlugin()])
