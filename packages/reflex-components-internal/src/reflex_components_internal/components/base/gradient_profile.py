"""Gradient profile component."""

import uuid

from reflex_base.components.component import Component
from reflex_base.vars.base import Var

from reflex.assets import asset
from reflex_components_internal.components.component import CoreComponent

DEFAULT_CLASS_NAME = "size-4 pointer-events-none rounded-full"
GRADIENT_PROFILE_ASSET_PATH = "GradientProfile.js"


class GradientProfile(CoreComponent):
    """Gradient profile component."""

    tag = "GradientProfile"

    # Seed to generate gradient for
    seed: Var[str | int | uuid.UUID]

    # Available colors for the gradient
    available_colors: Var[list[str]]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the gradient profile component.

        Returns:
            The component.
        """
        if "library" not in props:
            props["library"] = asset(
                path=GRADIENT_PROFILE_ASSET_PATH, shared=True
            ).importable_path
        cls.set_class_name(DEFAULT_CLASS_NAME, props)
        return super().create(*children, **props)


gradient_profile = GradientProfile.create
