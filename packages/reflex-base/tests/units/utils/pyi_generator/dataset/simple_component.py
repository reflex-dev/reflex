"""A simple component with basic props.

This module tests:
- Basic component stub generation
- Props with various simple types (str, int, bool, float)
- Default event handlers inherited from Component
- Props with doc strings (via field(doc=...))
- Props with comment-based docs (# comment above prop)
- Props with inline docstrings (triple-quoted string after prop)
- Module docstring removal in stubs
- visit_Assign: assignment to `Any` is preserved
- visit_Assign: non-annotated assignments are removed
"""

from typing import Any

from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var

# Assignment to Any should be preserved in the stub.
SomeType = Any

# A regular non-annotated assignment should be removed.
SOME_CONSTANT = 42


class SimpleComponent(Component):
    """A simple test component with basic prop types."""

    # The title displayed on the component.
    title: Var[str]

    # The count to display.
    count: Var[int]

    is_active: Var[bool] = field(doc="Whether the component is active.")

    opacity: Var[float] = field(doc="The opacity of the component.")

    label: Var[str] = field(
        default=Var.create("default"),
        doc="An optional label with a default value.",
    )

    description: Var[str]
    """A detailed description of the component."""

    tooltip: Var[str]
    """A tooltip that appears on hover
    with additional details."""

    callback: Var[str]
    """
    The def of the callback to use when the component is clicked.
    """

    def _private_method(self):
        """This should not appear in the stub.

        Returns:
            A string indicating this is a private method.
        """
        return "private"

    def public_helper(self) -> str:
        """A public method that should have its body blanked out.

        Returns:
            A string indicating this is a public helper method.
        """
        return "hello"
