"""Minimal repro: an rxe app with MCPPlugin, run with `reflex run --env prod` (deploy_url unset)."""

import os

import reflex as rx

assert os.environ.get("VE_VENV", "<unset>") in rx.__file__, rx.__file__

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="mcpmin",
    plugins=[rxe.MCPPlugin()],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
