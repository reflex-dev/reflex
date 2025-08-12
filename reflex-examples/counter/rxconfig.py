import reflex as rx

config = rx.Config(
    app_name="counter",
    db_url="sqlite:///reflex.db",
    env=rx.Env.DEV,
    tailwind=None,
)
