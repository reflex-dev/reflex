import reflex as rx

config = rx.Config(
    app_name="cliapp",
    frontend_compression_formats=["gzip", "brotli"],
)
