"""Skeleton theme from Radix components."""

from reflex.components.core.breakpoints import Responsive
from reflex.vars.base import Var

from ..base import RadixLoadingProp, RadixThemesComponent


class Skeleton(RadixLoadingProp, RadixThemesComponent):
    """Skeleton component."""

    tag = "Skeleton"

    # The width of the skeleton
    width: Var[Responsive[str]]

    # The minimum width of the skeleton
    min_width: Var[Responsive[str]]

    # The maximum width of the skeleton
    max_width: Var[Responsive[str]]

    # The height of the skeleton
    height: Var[Responsive[str]]

    # The minimum height of the skeleton
    min_height: Var[Responsive[str]]

    # The maximum height of the skeleton
    max_height: Var[Responsive[str]]


skeleton = Skeleton.create
