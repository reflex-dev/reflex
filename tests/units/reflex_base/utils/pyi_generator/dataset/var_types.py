"""Component with various Var[T] prop types.

This module tests:
- Var[T] expansion: Var[str] -> Var[str] | str
- Var with Union args: Var[str | int] -> Var[str | int] | str | int
- Optional props (None default)
- Complex nested types: Var[list[str]], Var[dict[str, Any]]
- Non-Var props (plain type annotations)
"""

from typing import Any

from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var


class VarTypesComponent(Component):
    """A component exercising various Var type expansions."""

    # Basic Var types.
    name: Var[str]
    count: Var[int]
    ratio: Var[float]
    flag: Var[bool]

    # Union inside Var.
    value: Var[str | int] = field(doc="A string or int value.")

    # Nested generic Var types.
    items: Var[list[str]] = field(doc="A list of string items.")
    metadata: Var[dict[str, Any]] = field(doc="Metadata dictionary.")
