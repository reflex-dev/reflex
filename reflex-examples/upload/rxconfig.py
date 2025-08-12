import reflex as rx


class UploadConfig(rx.Config):
    pass


config = UploadConfig(
    app_name="upload",
    db_url="sqlite:///reflex.db",
    env=rx.Env.DEV,
    tailwind=None,
)
