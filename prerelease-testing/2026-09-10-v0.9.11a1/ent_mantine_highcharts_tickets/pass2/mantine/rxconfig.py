"""Config for the Mantine demo app."""

import reflex as rx

config = rx.Config(
    app_name="mantine",
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
)
