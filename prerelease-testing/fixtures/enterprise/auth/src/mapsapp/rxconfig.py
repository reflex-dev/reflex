"""Enterprise maps test app (ent_auth cluster). Ports via APP_FP/APP_BP env (dev 3624/8624, prod 8625)."""

import os

import reflex_enterprise as rxe

FP = int(os.environ.get("APP_FP", "3624"))
BP = int(os.environ.get("APP_BP", "8624"))

config = rxe.Config(
    app_name="mapsapp",
    frontend_port=FP,
    backend_port=BP,
    telemetry_enabled=False,
)
