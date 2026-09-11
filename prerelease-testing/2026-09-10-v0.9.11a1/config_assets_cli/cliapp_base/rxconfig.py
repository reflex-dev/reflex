import reflex as rx

config = rx.Config(
    app_name="cliapp",
    # BACKEND-ONLY KNOB: flipped between runs to prove no frontend reinstall.
    cors_allowed_origins=["http://localhost:5300", "http://localhost:9700"],
    backend_host="127.0.0.1",
    telemetry_enabled=False,
)
