"""Skeleton theme from Radix components."""

from reflex.components.core.breakpoints import Responsive
from reflex.ivars.base import ImmutableVar

from ..base import RadixLoadingProp, RadixThemesComponent


class Skeleton(RadixLoadingProp, RadixThemesComponent):
    """Skeleton component."""

    tag = "Skeleton"

    # The width of the skeleton
    width: ImmutableVar[Responsive[str]]

    # The minimum width of the skeleton
    min_width: ImmutableVar[Responsive[str]]

    # The maximum width of the skeleton
    max_width: ImmutableVar[Responsive[str]]

    # The height of the skeleton
    height: ImmutableVar[Responsive[str]]

    # The minimum height of the skeleton
    min_height: ImmutableVar[Responsive[str]]

    # The maximum height of the skeleton
    max_height: ImmutableVar[Responsive[str]]


skeleton = Skeleton.create
