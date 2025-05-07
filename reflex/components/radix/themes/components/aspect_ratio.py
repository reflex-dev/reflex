"""Interactive components provided by @radix-ui/themes."""

from reflex.vars.base import Var

from ..base import RadixThemesComponent


class AspectRatio(RadixThemesComponent):
    """Displays content with a desired ratio."""

    tag = "AspectRatio"

    # The ratio of the width to the height of the element
    ratio: Var[float | int]


aspect_ratio = AspectRatio.create
