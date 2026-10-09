import reflex as rx

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="rxeapp",
    # Free/anonymous tier: hiding the badge must be refused (falls back to True with a warning).
    show_built_with_reflex=False,
    disable_plugins=[rx.plugins.SitemapPlugin],
)
