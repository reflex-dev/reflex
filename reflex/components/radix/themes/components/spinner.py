"""Radix Spinner Component."""

from typing import Literal

from reflex.components.component import field
from reflex.components.core.breakpoints import Responsive
from reflex.components.radix.themes.base import RadixLoadingProp, RadixThemesComponent
from reflex.vars.base import Var

LiteralSpinnerSize = Literal["1", "2", "3"]


class Spinner(RadixLoadingProp, RadixThemesComponent):
    """A spinner component."""

    tag = "Spinner"

    is_default = False

    size: Var[Responsive[LiteralSpinnerSize]] = field(doc="The size of the spinner.")


spinner = Spinner.create
