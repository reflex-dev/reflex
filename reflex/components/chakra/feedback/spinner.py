"""Container to stack elements with spacing."""
from typing import Optional

from reflex.components.chakra import ChakraComponent, LiteralSpinnerSize
from reflex.vars import Var


class Spinner(ChakraComponent):
    """The component that spins."""

    tag = "Spinner"

    # The color of the empty area in the spinner
    empty_color: Optional[Var[str]] = None

    # For accessibility, it is important to add a fallback loading text. This text will be visible to screen readers.
    label: Optional[Var[str]] = None

    # The speed of the spinner must be as a string and in seconds '1s'. Default is '0.45s'.
    speed: Optional[Var[str]] = None

    # The thickness of the spinner.
    thickness: Optional[Var[int]] = None

    # "xs" | "sm" | "md" | "lg" | "xl"
    size: Optional[Var[LiteralSpinnerSize]] = None
