"""Verifier app config: enterprise AuthPlugin (secure by default) + generic OIDC provider."""

import reflex_enterprise as rxe
from reflex_enterprise.plugins.auth import AuthPlugin

config = rxe.Config(
    app_name="vauth",
    plugins=[AuthPlugin()],
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
    telemetry_enabled=False,
)
