"""Configuration for the ag_grid demo."""

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="ag_grid",
    async_db_url="sqlite+aiosqlite:///reflex.db",
    use_single_port=True,
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
)
