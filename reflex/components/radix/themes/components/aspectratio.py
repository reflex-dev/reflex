"""Interactive components provided by @radix-ui/themes."""
from typing import Literal, Union

from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    RadixThemesComponent,
)

LiteralSwitchSize = Literal["1", "2", "3", "4"]


class AspectRatio(CommonMarginProps, RadixThemesComponent):
    """A toggle switch alternative to the checkbox."""

    tag = "AspectRatio"

    # The ratio of the width to the height of the element
    ratio: Var[Union[float, int]]
