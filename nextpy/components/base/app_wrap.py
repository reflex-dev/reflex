"""Top-level component that wraps the entire app."""
from nextpy.components.component import Component

from .bare import Bare


class AppWrap(Bare):
    """Top-level component that wraps the entire app."""

    @classmethod
    def create(cls) -> Component:
        """Create a new AppWrap component.

        Returns:
            A new AppWrap component containing {children}.
        """
        return super().create(contents="{children}")
