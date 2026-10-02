"""Skeleton theme from Radix components."""

from reflex_base.components.component import field
from reflex_base.constants.compiler import MemoizationMode
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import RadixLoadingProp, RadixThemesComponent


class Skeleton(RadixLoadingProp, RadixThemesComponent):
    """Skeleton component."""

    tag = "Skeleton"

    width: Var[Responsive[str]] = field(doc="The width of the skeleton")

    min_width: Var[Responsive[str]] = field(doc="The minimum width of the skeleton")

    max_width: Var[Responsive[str]] = field(doc="The maximum width of the skeleton")

    height: Var[Responsive[str]] = field(doc="The height of the skeleton")

    min_height: Var[Responsive[str]] = field(doc="The minimum height of the skeleton")

    max_height: Var[Responsive[str]] = field(doc="The maximum height of the skeleton")

    _memoization_mode = MemoizationMode(recursive=False)


skeleton = Skeleton.create
