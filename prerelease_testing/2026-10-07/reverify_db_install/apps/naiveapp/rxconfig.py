import reflex as rx

config = rx.Config(
    app_name="naiveapp",
    db_url="sqlite:///reflex.db",
    telemetry_enabled=False,
)
