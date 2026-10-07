import os

import reflex_enterprise as rxe

# a3_ent_grid guard: reflex must import from the venv start.sh was asked to use (never from a checkout).
import reflex as _rx_guard

assert "/scratchpad/envs/" in _rx_guard.__file__, _rx_guard.__file__
if os.environ.get("VERIFY_VENV"):
    assert f"/scratchpad/envs/{os.environ['VERIFY_VENV']}/" in _rx_guard.__file__, (_rx_guard.__file__, os.environ["VERIFY_VENV"])

_port = os.environ.get("VERIFY_BACKEND_PORT", "8300")

config = rxe.Config(
    app_name="entr",
    api_url=f"http://localhost:{_port}",
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
)
