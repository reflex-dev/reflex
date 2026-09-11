import os

import reflex as rx
from reflex_base.plugins.base import Plugin


class LucideBundlePlugin(Plugin):
    """Declare lucide-react as a frontend dependency (the supported plugin route)."""

    def get_frontend_dependencies(self, **context):
        """Return the packages this plugin needs bundled.

        Args:
            context: Plugin context.

        Returns:
            The package list.
        """
        return ["lucide-react@1.26.0"]


plugins = [LucideBundlePlugin()] if os.environ.get("REPRO_PLUGIN") == "1" else []

config = rx.Config(app_name="dynmin", plugins=plugins)
