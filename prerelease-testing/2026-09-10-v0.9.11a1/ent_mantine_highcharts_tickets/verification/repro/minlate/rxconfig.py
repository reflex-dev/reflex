"""Minimal pure-reflex repro: a plugin that registers a state in post_compile."""

import reflex as rx
from reflex.plugins.base import Plugin


class LateStatePlugin(Plugin):
    """Registers an rx.State subclass from the post_compile hook."""

    def post_compile(self, **context) -> None:
        """Import a module that defines an rx.State subclass.

        Args:
            context: The plugin context.
        """
        import late_state  # noqa: F401


config = rx.Config(app_name="minlate", plugins=[LateStatePlugin()])
