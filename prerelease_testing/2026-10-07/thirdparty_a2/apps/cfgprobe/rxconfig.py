import reflex as rx

# Values that differ from the defaults, read back inside a backend event handler.
config = rx.Config(
    app_name="cfgprobe",
    state_auto_setters=True,
    redis_lock_expiration=12345,
    default_color_mode="dark",
    telemetry_enabled=False,
    plugins=[rx.plugins.SitemapPlugin(), rx.plugins.RadixThemesPlugin()],
)
