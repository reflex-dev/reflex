"""Minimal repro: rxe.ag_grid API calls through refs (grid.api.* / AgGridAPI.create(id))."""

import os

import reflex as rx

assert os.environ.get("VE_VENV", "<unset>") in rx.__file__, rx.__file__

import reflex_enterprise as rxe

config = rxe.Config(app_name="agapi_memo3", disable_plugins=[rx.plugins.SitemapPlugin])
