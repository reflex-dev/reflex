"""Gradient profile component."""

from reflex.components.component import Component
from reflex.vars.base import Var
from reflex_ui.components.component import CoreComponent

DEFAULT_CLASS_NAME = "size-4 pointer-events-none rounded-full"


class GradientProfile(CoreComponent):
    """Gradient profile component."""

    library = "@carlosabadia/gradient-profile@github:carlosabadia/gradient-profile"

    tag = "GradientProfile"

    # Seed to generate gradient for
    seed: Var[str | int]

    # Available colors
    available_colors: Var[list[str]]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the gradient profile component.

        Returns:
            The component.
        """
        cls.set_class_name(DEFAULT_CLASS_NAME, props)
        return super().create(*children, **props)


gradient_profile = GradientProfile.create
