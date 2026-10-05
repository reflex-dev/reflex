import os

import reflex as rx

config = rx.Config(
    app_name="bpapp",
    frontend_path="/app",
    frontend_lazy_bundled_libraries=os.environ.get("BP_LAZY", "0") == "1",
    api_url=os.environ.get("BP_API_URL", "http://localhost:8260"),
    telemetry_enabled=False,
)
