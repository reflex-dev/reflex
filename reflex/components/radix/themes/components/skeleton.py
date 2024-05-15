"""Skeleton theme from Radix components."""

from reflex.vars import Var

from ..base import RadixLoadingProp, RadixThemesComponent


class Skeleton(RadixLoadingProp, RadixThemesComponent):
    """Skeleton component."""

    tag = "Skeleton"

    # The width of the skeleton
    width: Var[str]

    # The minimum width of the skeleton
    min_width: Var[str]

    # The maximum width of the skeleton
    max_width: Var[str]

    # The height of the skeleton
    height: Var[str]

    # The minimum height of the skeleton
    min_height: Var[str]

    # The maximum height of the skeleton
    max_height: Var[str]


skeleton = Skeleton.create
