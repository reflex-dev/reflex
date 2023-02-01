"""Create a Prop Condition."""
from typing import Any

from pynecone import utils
from pynecone.base import Base
from pynecone.var import Var


class PropCond(Base):
    """A conditional prop."""

    # The condition to determine which prop to render.
    cond: Var[Any]

    # The prop to render if the condition is true.
    prop1: Any

    # The prop to render if the condition is false.
    prop2: Any

    @classmethod
    def create(cls, cond: Var, prop1: Any, prop2: Any = None):
        """Create a conditional Prop.

        Args:
            cond: The cond to determine which prop to render.
            prop1: The prop value to render if the cond is true.
            prop2: The prop value to render if the cond is false.

        Returns:
            The conditional Prop.
        """
        return cls(
            cond=cond,
            prop1=prop1,
            prop2=prop2,
        )

    def __str__(self) -> str:
        """Render the prop as a React string.

        Returns:
            The React code to render the prop.
        """
        assert self.cond is not None, "The condition must be set."
        return utils.format_cond(
            cond=self.cond.full_name,
            true_value=self.prop1,
            false_value=self.prop2,
            is_prop=True,
        )
