"""verify_ent_auth app config: enterprise AuthPlugin, secure by default (auth=True)."""

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="vea",
    plugins=[rxe.AuthPlugin()],
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
)
