"""Top-level component that wraps the entire app."""

from reflex_base.components.component import Component
from reflex_base.vars.base import Var

from reflex_components_core.base.fragment import Fragment


class AppWrap(Fragment):
    """Top-level component that wraps the entire app."""

    @classmethod
    def create(cls) -> Component:
        """Create a new AppWrap component.

        Returns:
            A new AppWrap component containing {children}.
        """
        return super().create(Var(_js_expr="children"))
