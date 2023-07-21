"""The Radix progress component."""
from typing import Optional

from reflex.components import Component


class ProgressComponent(Component):
    """Base class for all progress components."""

    library = "@radix-ui/react-progress"
    is_default = False

    as_child: Optional[bool]


class ProgressRoot(ProgressComponent):
    """Radix progress root."""

    tag = "Root"
    alias = "ProgressRoot"

    value: Optional[float]
    max: Optional[float]


class ProgressIndicator(ProgressComponent):
    """Radix progress indicator."""

    tag = "Indicator"
    alias = "ProgressIndicator"
