"""Reflex configuration of the playground app."""

import os
from pathlib import Path

import reflex as rx

plugins: list[rx.plugins.Plugin] = [rx.plugins.SitemapPlugin()]
# Reflex 0.9 moved Radix Themes into a plugin, which takes the theme; older
# releases always load it and take the theme from rx.App (playground.py).
if hasattr(rx.plugins, "RadixThemesPlugin"):
    plugins.append(rx.plugins.RadixThemesPlugin(theme=rx.theme(accent_color="violet")))
# Tailwind is on by default, as `reflex init` sets it up; PLAYGROUND_TAILWIND=0
# builds without it.
if os.environ.get("PLAYGROUND_TAILWIND", "1") == "1":
    plugins.append(rx.plugins.TailwindV4Plugin())

config = rx.Config(
    app_name="playground",
    # An absolute path, so every working directory uses the same database file.
    db_url=f"sqlite:///{Path(__file__).resolve().parent / 'playground.db'}",
    plugins=plugins,
)
