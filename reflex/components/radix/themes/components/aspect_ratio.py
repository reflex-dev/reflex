"""Interactive components provided by @radix-ui/themes."""

from reflex.components.radix.themes.base import RadixThemesComponent
from reflex.vars.base import Var


class AspectRatio(RadixThemesComponent):
    """Displays content with a desired ratio."""

    tag = "AspectRatio"

    # The ratio of the width to the height of the element
    ratio: Var[float | int]


aspect_ratio = AspectRatio.create
