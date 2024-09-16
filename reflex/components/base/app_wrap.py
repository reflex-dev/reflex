"""Top-level component that wraps the entire app."""

from reflex.components.base.fragment import Fragment
from reflex.components.component import Component
from reflex.vars.base import Var


class AppWrap(Fragment):
    """Top-level component that wraps the entire app."""

    @classmethod
    def create(cls) -> Component:
        """Create a new AppWrap component.

        Returns:
            A new AppWrap component containing {children}.
        """
        return super().create(Var(_js_expr="children"))
