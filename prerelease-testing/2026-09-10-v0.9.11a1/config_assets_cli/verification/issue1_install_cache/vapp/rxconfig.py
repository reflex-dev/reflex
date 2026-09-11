import reflex as rx

config = rx.Config(
    app_name="vapp",
    telemetry_enabled=False,
    # BACKEND-ONLY change #2 (different from run 2):
    backend_host="127.0.0.1",
    cors_allowed_origins=["http://localhost:6001", "http://localhost:10400"],
    backend_port=10400,
)
