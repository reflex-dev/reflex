"""Radix Spinner Component."""

from typing import Literal

from reflex.vars import Var

from ..base import (
    RadixLoadingProp,
    RadixThemesComponent,
)

LiteralSpinnerSize = Literal["1", "2", "3"]


class Spinner(RadixLoadingProp, RadixThemesComponent):
    """A spinner component."""

    tag = "Spinner"

    is_default = False

    # The size of the spinner.
    size: Var[LiteralSpinnerSize]


spinner = Spinner.create
