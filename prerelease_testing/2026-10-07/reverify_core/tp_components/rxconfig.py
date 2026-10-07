import reflex as rx

config = rx.Config(
    app_name="tp_components",
    # reflex-dynoselect relies on the generated set_<var> setters (set_search_phrase).
    state_auto_setters=True,
    plugins=[rx.plugins.SitemapPlugin(), rx.plugins.RadixThemesPlugin()],
)
