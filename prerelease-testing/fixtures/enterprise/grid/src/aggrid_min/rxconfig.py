import os

import reflex as rx

import reflex_enterprise as rxe

# venv guard: reflex must import from the venv start.sh was asked to use (never from a checkout).
assert "/envs/" in rx.__file__, rx.__file__
if os.environ.get("VERIFY_VENV"):
    assert f"/envs/{os.environ['VERIFY_VENV']}/" in rx.__file__, (rx.__file__, os.environ["VERIFY_VENV"])

config = rxe.Config(app_name="aggrid_min", disable_plugins=[rx.plugins.SitemapPlugin])
