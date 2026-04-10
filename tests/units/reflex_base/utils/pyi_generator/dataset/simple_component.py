"""A simple component with basic props.

This module tests:
- Basic component stub generation
- Props with various simple types (str, int, bool, float)
- Default event handlers inherited from Component
- Props with doc strings (via field(doc=...))
- Props with comment-based docs (# comment above prop)
- Module docstring removal in stubs
"""

from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var


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

    def _private_method(self):
        """This should not appear in the stub."""
        return "private"

    def public_helper(self) -> str:
        """A public method that should have its body blanked out."""
        return "hello"
