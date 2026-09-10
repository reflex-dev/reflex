import reflex as rx


class UploadConfig(rx.Config):
    pass


config = UploadConfig(
    app_name="upload",
    env=rx.Env.DEV,
    plugins=[rx.plugins.RadixThemesPlugin()],
)
