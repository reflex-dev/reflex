"""Radix Spinner Component."""

from typing import Literal

from reflex.components.core.breakpoints import Responsive
from reflex.components.radix.themes.base import RadixLoadingProp, RadixThemesComponent
from reflex.vars.base import Var

LiteralSpinnerSize = Literal["1", "2", "3"]


class Spinner(RadixLoadingProp, RadixThemesComponent):
    """A spinner component."""

    tag = "Spinner"

    is_default = False

    # The size of the spinner.
    size: Var[Responsive[LiteralSpinnerSize]]


spinner = Spinner.create
