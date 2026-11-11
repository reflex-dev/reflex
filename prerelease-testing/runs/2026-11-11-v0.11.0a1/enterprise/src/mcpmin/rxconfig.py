"""Minimal repro: an rxe app with MCPPlugin, run with `reflex run --env prod` (deploy_url unset)."""

import reflex as rx

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="mcpmin",
    plugins=[rxe.MCPPlugin()],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
