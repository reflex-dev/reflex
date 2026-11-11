import os

import reflex as rx

kw = {}
if t := os.environ.get("NA_TRANSPORT"):
    kw["transport"] = t
if p := os.environ.get("NA_CFG_FRONTEND_PORT"):
    kw["frontend_port"] = int(p)
if p := os.environ.get("NA_CFG_BACKEND_PORT"):
    kw["backend_port"] = int(p)
if th := os.environ.get("NA_CFG_BLOCK_THRESHOLD"):
    kw["event_loop_blocking_threshold"] = float(th)

config = rx.Config(
    app_name="netapp",
    plugins=[rx.plugins.SitemapPlugin()],
    disable_plugins=["reflex.plugins.tailwind_v4.TailwindV4Plugin"],
    **kw,
)
