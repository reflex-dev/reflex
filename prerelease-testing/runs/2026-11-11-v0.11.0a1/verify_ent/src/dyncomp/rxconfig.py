"""Issue 4 control without reflex-enterprise: Component-valued state vars + an rx.Model."""

import os

import reflex as rx

assert os.environ.get("VE_VENV", "<unset>") in rx.__file__, rx.__file__

config = rx.Config(app_name="dyncomp", db_url="sqlite:///reflex.db", plugins=[rx.plugins.RadixThemesPlugin()], disable_plugins=[rx.plugins.SitemapPlugin])
