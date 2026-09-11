"""Minimal rxe config for the hydrate-delta verification."""

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="minrx",
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
)
