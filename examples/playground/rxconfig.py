"""Reflex configuration of the playground app."""

import reflex as rx

plugins: list[rx.plugins.Plugin] = [rx.plugins.SitemapPlugin()]
# Reflex 0.9 moved Radix Themes into a plugin; older releases always load it.
if hasattr(rx.plugins, "RadixThemesPlugin"):
    plugins.append(rx.plugins.RadixThemesPlugin())

config = rx.Config(app_name="playground", plugins=plugins)
