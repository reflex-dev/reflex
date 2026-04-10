"""Module with assignments to Any and dunder assignments.

This module tests:
- visit_Assign: assignment to `Any` is preserved
- visit_Assign: dunder tuple assignments are removed (lazy_loader.attach pattern)
- Non-Component classes are not processed (no create() added)
"""

from typing import Any

from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var

# Assignment to Any should be preserved in the stub.
SomeType = Any

# A regular non-annotated assignment should be removed.
SOME_CONSTANT = 42


class SmallComponent(Component):
    """A small component."""

    text: Var[str] = field(doc="The text content.")
