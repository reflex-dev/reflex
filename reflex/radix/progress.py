"""The Radix progress component."""
from reflex.components import Component
from reflex.vars import Var


class ProgressComponent(Component):
    """Base class for all progress components."""

    library = "@radix-ui/react-progress"
    is_default = False

    as_child: Var[bool]


class ProgressRoot(ProgressComponent):
    """Radix progress root."""

    tag = "Root"
    alias = "ProgressRoot"

    value: Var[float]
    max: Var[float]


class ProgressIndicator(ProgressComponent):
    """Radix progress indicator."""

    tag = "Indicator"
    alias = "ProgressIndicator"
