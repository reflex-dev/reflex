"""Interactive components provided by @radix-ui/themes."""

from typing import Union

from reflex.vars.base import Var

from ..base import RadixThemesComponent


class AspectRatio(RadixThemesComponent):
    """Displays content with a desired ratio."""

    tag = "AspectRatio"

    # The ratio of the width to the height of the element
    ratio: Var[Union[float, int]]


aspect_ratio = AspectRatio.create
