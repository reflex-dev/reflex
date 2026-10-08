"""Verifier app config: enterprise AuthPlugin (secure by default) + generic OIDC provider."""

import reflex_enterprise as rxe
from reflex_enterprise.plugins.auth import AuthPlugin

config = rxe.Config(
    app_name="vauth",
    plugins=[AuthPlugin()],
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
    telemetry_enabled=False,
)

import os as _qa_os  # noqa: E402

import reflex as _qa_rx  # noqa: E402

_qa_ev = _qa_os.environ.get("QA_EXPECT_VENV")
if _qa_ev:  # QA venv guard (a4_upgrade_ent)
    assert f"/scratchpad/envs/{_qa_ev}/" in _qa_rx.__file__, _qa_rx.__file__
