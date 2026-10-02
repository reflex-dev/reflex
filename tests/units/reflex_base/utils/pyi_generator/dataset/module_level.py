"""Module with module-level functions, constants, and type aliases.

This module tests:
- Module-level function body blanking
- Module-level annotated assignments (value blanked)
- Module-level non-annotated assignments (removed)
- Type alias preservation
- Combined: component + module-level items
"""

from typing import Literal

from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var

LiteralMode = Literal["light", "dark", "system"]

# A module-level constant (non-annotated, should be removed).
DEFAULT_TIMEOUT = 30

# Annotated module-level var (value should be blanked).
current_mode: LiteralMode = "system"


def helper_function(x: int, y: int) -> int:
    """Add two numbers.

    Args:
        x: First number.
        y: Second number.

    Returns:
        The sum.
    """
    return x + y


def another_helper() -> None:
    """Do nothing important."""
    print("side effect")


class ModuleComponent(Component):
    """A component defined alongside module-level items."""

    mode: Var[LiteralMode] = field(doc="The display mode.")

    timeout: Var[int] = field(doc="Timeout in seconds.")
