import os

import reflex as rx

_qa_ev = os.environ.get("QA_EXPECT_VENV")
if _qa_ev:  # QA venv guard (a5_upgrade_ent)
    assert f"/scratchpad/envs/{_qa_ev}/" in rx.__file__, rx.__file__

config = rx.Config(app_name="azapp", telemetry_enabled=False, disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"])
