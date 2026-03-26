"""Interactive components provided by @radix-ui/themes."""

from reflex_core.components.component import field
from reflex_core.vars.base import Var

from reflex_components_radix.themes.base import RadixThemesComponent


class AspectRatio(RadixThemesComponent):
    """Displays content with a desired ratio."""

    tag = "AspectRatio"

    ratio: Var[float | int] = field(
        doc="The ratio of the width to the height of the element"
    )


aspect_ratio = AspectRatio.create
