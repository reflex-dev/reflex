"""Minimal repro: rxe.ag_grid API calls through refs (grid.api.* / AgGridAPI.create(id))."""

import reflex as rx

import reflex_enterprise as rxe

config = rxe.Config(app_name="agapi", disable_plugins=[rx.plugins.SitemapPlugin])
