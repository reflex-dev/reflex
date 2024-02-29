"""Interactive components provided by @radix-ui/themes."""
from typing import Optional, Union

from reflex.vars import Var

from ..base import RadixThemesComponent


class AspectRatio(RadixThemesComponent):
    """Displays content with a desired ratio."""

    tag = "AspectRatio"

    # The ratio of the width to the height of the element
    ratio: Optional[Var[Union[float, int]]] = None


aspect_ratio = AspectRatio.create
