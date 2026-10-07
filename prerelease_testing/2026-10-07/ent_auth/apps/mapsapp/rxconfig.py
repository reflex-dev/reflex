"""Enterprise maps test app (ent_auth cluster). Ports via APP_FP/APP_BP env (dev 3344/8344, prod 8345)."""

import os

import reflex_enterprise as rxe

FP = int(os.environ.get("APP_FP", "3344"))
BP = int(os.environ.get("APP_BP", "8344"))

config = rxe.Config(
    app_name="mapsapp",
    frontend_port=FP,
    backend_port=BP,
    telemetry_enabled=False,
)
