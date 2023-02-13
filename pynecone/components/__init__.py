"""Import all the components."""
from __future__ import annotations

from typing import TYPE_CHECKING

from pynecone import utils

from .component import Component
from .datadisplay import *
from .disclosure import *
from .feedback import *
from .forms import *
from .graphing import *
from .layout import *
from .media import *
from .navigation import *
from .overlay import *
from .typography import *

if TYPE_CHECKING:
    from typing import Any

# Add the convenience methods for all the components.
locals().update(
    {
        utils.to_snake_case(name): value.create
        for name, value in locals().items()
        if isinstance(value, type) and issubclass(value, Component)
    }
)


# Add responsive styles shortcuts.
def mobile_only(*children, **props):
    """Create a component that is only visible on mobile.

    Args:
        *children: The children to pass to the component.
        **props: The props to pass to the component.

    Returns:
        The component.
    """
    return Box.create(*children, **props, display=["block", "none", "none", "none"])


def tablet_only(*children, **props):
    """Create a component that is only visible on tablet.

    Args:
        *children: The children to pass to the component.
        **props: The props to pass to the component.

    Returns:
        The component.
    """
    return Box.create(*children, **props, display=["none", "block", "block", "none"])


def desktop_only(*children, **props):
    """Create a component that is only visible on desktop.

    Args:
        *children: The children to pass to the component.
        **props: The props to pass to the component.

    Returns:
        The component.
    """
    return Box.create(*children, **props, display=["none", "none", "none", "block"])


def tablet_and_desktop(*children, **props):
    """Create a component that is only visible on tablet and desktop.

    Args:
        *children: The children to pass to the component.
        **props: The props to pass to the component.

    Returns:
        The component.
    """
    return Box.create(*children, **props, display=["none", "block", "block", "block"])


def mobile_and_tablet(*children, **props):
    """Create a component that is only visible on mobile and tablet.

    Args:
        *children: The children to pass to the component.
        **props: The props to pass to the component.

    Returns:
        The component.
    """
    return Box.create(*children, **props, display=["block", "block", "block", "none"])


def cond(condition: Any, c1: Any, c2: Any = None):
    """Create a conditional component or Prop.

    Args:
        condition: The cond to determine which component to render.
        c1: The component or prop to render if the cond_var is true.
        c2: The component or prop to render if the cond_var is false.

    Returns:
        The conditional component.

    Raises:
        ValueError: If the arguments are invalid.
    """
    # Import here to avoid circular imports.
    from pynecone.var import BaseVar, Var

    # Convert the condition to a Var.
    cond_var = Var.create(condition)
    assert cond_var is not None, "The condition must be set."

    # If the first component is a component, create a Cond component.
    if isinstance(c1, Component):
        assert c2 is None or isinstance(
            c2, Component
        ), "Both arguments must be components."
        return Cond.create(cond_var, c1, c2)

    # Otherwise, create a conditionl Var.
    # Check that the second argument is valid.
    if isinstance(c2, Component):
        raise ValueError("Both arguments must be props.")
    if c2 is None:
        raise ValueError("For conditional vars, the second argument must be set.")

    # Create the conditional var.
    return BaseVar(
        name=utils.format_cond(
            cond=cond_var.full_name,
            true_value=c1,
            false_value=c2,
            is_prop=True,
        ),
        type_=c1.type_ if isinstance(c1, BaseVar) else type(c1),
    )
