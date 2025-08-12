import reflex as rx

config = rx.Config(
    app_name="snakegame",
    db_url="sqlite:///reflex.db",
    env=rx.Env.DEV,
    tailwind=None,
)
