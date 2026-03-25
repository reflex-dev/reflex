"""Skeleton theme from Radix components."""

from reflex.components.component import field
from reflex.components.core.breakpoints import Responsive
from reflex.components.radix.themes.base import RadixLoadingProp, RadixThemesComponent
from reflex.constants.compiler import MemoizationMode
from reflex.vars.base import Var


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
