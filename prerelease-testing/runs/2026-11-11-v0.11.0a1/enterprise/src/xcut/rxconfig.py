"""xcut: cross-cutting checks of reflex-enterprise 0.9.11 against reflex 0.11 (CORS, lifespan, awaited handlers, REST/WS parity, Redis).

Env knobs:
  XC_FP / XC_BP        frontend / backend ports (required)
  XC_DEPLOY_URL        rxe.Config(deploy_url=...)
  XC_CORS              comma list -> rxe.Config(cors_allowed_origins=[...])
  XC_AUTH=0            drop AuthPlugin (default on: OIDC via OIDC_ISSUER_URI etc.)
  XC_MCP=0             drop MCPPlugin
  XC_SINGLE=1          rxe.Config(use_single_port=True)
  XC_EXPECT_VENV       venv guard (name under $SB/envs)
"""

import os

import reflex as rx

import reflex_enterprise as rxe

_ev = os.environ.get("XC_EXPECT_VENV")
if _ev:
    assert f"/envs/{_ev}/" in rx.__file__, rx.__file__

kw = {}
if os.environ.get("XC_DEPLOY_URL"):
    kw["deploy_url"] = os.environ["XC_DEPLOY_URL"]
if os.environ.get("XC_CORS"):
    kw["cors_allowed_origins"] = os.environ["XC_CORS"].split(",")
if os.environ.get("XC_SINGLE") == "1":
    kw["use_single_port"] = True

plugins = [rxe.EventHandlerAPIPlugin()]
if os.environ.get("XC_MCP", "1") == "1":
    plugins.append(rxe.MCPPlugin())
if os.environ.get("XC_AUTH", "1") == "1":
    plugins.insert(0, rxe.AuthPlugin())

config = rxe.Config(
    app_name="xcut",
    frontend_port=int(os.environ["XC_FP"]),
    backend_port=int(os.environ["XC_BP"]),
    telemetry_enabled=False,
    plugins=plugins,
    disable_plugins=[rx.plugins.SitemapPlugin],
    **kw,
)
