"""FINDING-021 repro: rxe single-port dev proxy (frontend proxied through the backend port)."""

import os

import reflex as rx

assert os.environ.get("VE_VENV", "<unset>") in rx.__file__, rx.__file__

import reflex_enterprise as rxe

config = rxe.Config(app_name="single", use_single_port=True, disable_plugins=[rx.plugins.SitemapPlugin])
