"""Interactive components provided by @radix-ui/themes."""

from typing import Union

from reflex.ivars.base import ImmutableVar

from ..base import RadixThemesComponent


class AspectRatio(RadixThemesComponent):
    """Displays content with a desired ratio."""

    tag = "AspectRatio"

    # The ratio of the width to the height of the element
    ratio: ImmutableVar[Union[float, int]]


aspect_ratio = AspectRatio.create
