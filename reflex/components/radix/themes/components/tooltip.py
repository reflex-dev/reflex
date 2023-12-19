"""Interactive components provided by @radix-ui/themes."""
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    RadixThemesComponent,
)


class Tooltip(CommonMarginProps, RadixThemesComponent):
    
    tag = "Tooltip"

    content: Var[str]