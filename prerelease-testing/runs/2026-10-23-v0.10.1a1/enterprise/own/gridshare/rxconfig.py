import os

import reflex_enterprise as rxe

config = rxe.Config(app_name="gridshare", telemetry_enabled=False, disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"])

import reflex as _qa_rx  # noqa: E402

_qa_ev = os.environ.get("QA_EXPECT_VENV")
if _qa_ev:  # QA venv guard
    assert f"/envs/{_qa_ev}/" in _qa_rx.__file__, _qa_rx.__file__
