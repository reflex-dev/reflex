"""Component with an explicitly defined create() method.

This module tests:
- Existing create() is regenerated (replaced with generated version)
- Decorator list from original create() is preserved
- Custom kwargs on create() are included
"""

from typing import Any

from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var


class CustomCreateComponent(Component):
    """A component that defines its own create method."""

    # A label prop.
    label: Var[str] = field(doc="Display label.")

    # A numeric value.
    amount: Var[int] = field(doc="The amount.")

    @classmethod
    def create(
        cls, *children: Any, custom_kwarg: str = "default", **props: Any
    ) -> "CustomCreateComponent":
        """Create a custom component with extra kwargs.

        Args:
            *children: The child components.
            custom_kwarg: A custom keyword argument.
            **props: Additional properties.

        Returns:
            The component instance.
        """
        return super().create(*children, **props)
