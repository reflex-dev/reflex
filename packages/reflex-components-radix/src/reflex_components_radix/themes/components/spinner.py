"""Radix Spinner Component."""

from typing import Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import RadixLoadingProp, RadixThemesComponent

LiteralSpinnerSize = Literal["1", "2", "3"]


class Spinner(RadixLoadingProp, RadixThemesComponent):
    """A spinner component."""

    tag = "Spinner"

    is_default = False

    size: Var[Responsive[LiteralSpinnerSize]] = field(doc="The size of the spinner.")


spinner = Spinner.create
