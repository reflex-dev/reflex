"""A skeleton placeholder for loading content."""

from __future__ import annotations

from typing import ClassVar

from reflex_components_core.el.elements.typography import Div
from reflex_components_core.ui.base import UIComponent

SKELETON_CLASS_NAME = "bg-accent animate-pulse rounded-md"


class Skeleton(Div, UIComponent):
    """An animated placeholder shown while content loads.

    Size it with Tailwind classes, e.g. ``class_name="h-4 w-32"``.
    """

    _slot: ClassVar[str | None] = "skeleton"

    @classmethod
    def create(cls, *children, **props):
        """Create a skeleton.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The skeleton component.
        """
        cls._apply_class_name(SKELETON_CLASS_NAME, props)
        return super().create(*children, **props)


skeleton = Skeleton.create
