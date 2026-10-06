import reflex as rx

config = rx.Config(
    app_name="tp_patterns",
    # setvar() needs the generated set_<var> setters.
    state_auto_setters=True,
    plugins=[rx.plugins.SitemapPlugin(), rx.plugins.RadixThemesPlugin()],
)
