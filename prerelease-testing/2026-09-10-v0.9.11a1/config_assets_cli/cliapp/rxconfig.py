import reflex as rx

config = rx.Config(
    app_name="cliapp",
    # BACKEND-ONLY KNOB: flipped between runs to prove no frontend reinstall.
    cors_allowed_origins=["http://localhost:5300", "http://localhost:9700"],
    backend_host="0.0.0.0",
    telemetry_enabled=False,
    plugins=[rx.plugins.TailwindV4Plugin(), rx.plugins.SitemapPlugin()],
)
