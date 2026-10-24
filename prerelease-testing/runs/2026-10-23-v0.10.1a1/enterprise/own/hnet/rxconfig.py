"""XFF / client_ip probe app for the enterprise item (#7614 vs rxe 0.9.8 REST event API).

REFLEX_TRUSTED_PROXY_HOPS=<n> (0.10.1a1 only) sets reflex's trusted_proxy_hops via the env path;
XFF_RXE_HOPS=<n> sets the rxe plugin's own trusted_proxy_hops (rate limiters).
"""
import os

import reflex_enterprise as rxe

_rxe_hops = int(os.environ.get("XFF_RXE_HOPS", "0"))
config = rxe.Config(
    app_name="hnet",
    telemetry_enabled=False,
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
    plugins=[rxe.EventHandlerAPIPlugin(token_rate_limit=0, trusted_proxy_hops=_rxe_hops)],
)

import reflex as _qa_rx  # noqa: E402

_qa_ev = os.environ.get("QA_EXPECT_VENV")
if _qa_ev:  # QA venv guard
    assert f"/envs/{_qa_ev}/" in _qa_rx.__file__, _qa_rx.__file__
