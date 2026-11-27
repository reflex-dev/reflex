"""The harness app as a project, to look at its pages by hand."""

import reflex as rx

config = rx.Config(
    app_name="ui_parity",
    plugins=[rx.plugins.UIPlugin(), rx.plugins.TailwindV4Plugin()],
    # The badge floats over the page, and over whatever cell lies under it.
    show_built_with_reflex=False,
)
